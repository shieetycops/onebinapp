"""Trending (SPEC_TRENDING.md), shared by build_catalog.py and build_ai.py. Stdlib only, no network at import time.

Core signal = star growth between our own history snapshots (data/history/*snapshot-YYYY-MM-DD.json, {repo: {stars,...}}).
  d7  = stars_now - stars at the snapshot closest to 7 days ago, accepted only if it is 6..9 days old
  d30 = same for 30 days, accepted only if 27..33 days old
  Not enough history => None (never 0).  ready = at least one repo has d7 not None.
Rank: repos with d7 > 0 (growth; a flat or shrinking repo is not 'rising'), by d7 desc, ties by d30 desc (None last), then stars desc.
Top TOP_N get rank 1..n.  Badge 'naik daun' (decided on the site from card fields): rank not None and d7 >= max(5, 1% of stars).
Downloads and Trendshift are NOT used (see SPEC_TRENDING.md).

github.com/trending is OPT-IN (--with-github-trending). get_github_trending() is only ever called when that flag is set.
At most 2 HTTP requests per call in total (daily, weekly; a retry spends from the same budget), identifying User-Agent, tolerant parser, ANY failure => ok False with empty lists."""
import re, json, time, glob, pathlib, datetime, urllib.request, html as _html

WINDOWS = {7: (6, 9), 30: (27, 33)}
TOP_N = 50
BADGE_MIN_D7 = 5
BADGE_PCT = 0.01
UA = 'jembatan-rilis-catalog/1.0 (opt-in trending read, max 2 requests per build; static catalog builder)'
GH_TRENDING = {'daily': 'https://github.com/trending?since=daily', 'weekly': 'https://github.com/trending?since=weekly'}
CACHE_HOURS = 6
FORBIDDEN = re.compile(r'\b(' + 'am' + 'an' + r'|' + 'sa' + 'fe' + r')\b', re.I)


# ------------------------------------------------------------------ star history
def load_snapshots(hist_dir, prefix=''):
    """-> {date: {repo_lower: {...}}} for files <prefix>snapshot-YYYY-MM-DD.json (prefix '' or 'ai-')."""
    snaps = {}
    name = prefix + 'snapshot-'
    for f in sorted(glob.glob(str(pathlib.Path(hist_dir) / (name + '*.json')))):
        stem = pathlib.Path(f).stem
        if not stem.startswith(name): continue
        try:
            d = datetime.date.fromisoformat(stem[len(name):])
            raw = json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
        except Exception:
            continue
        if isinstance(raw, dict):
            snaps[d] = {str(k).lower(): v for k, v in raw.items() if isinstance(v, dict)}
    return snaps


def pick_baseline(snaps, today, window):
    """Snapshot date closest to `window` days ago within the accepted age range, else None (ties -> the older one)."""
    lo, hi = WINDOWS[window]
    best = None
    for d in snaps:
        age = (today - d).days
        if lo <= age <= hi:
            key = (abs(age - window), -age)
            if best is None or key < best[0]: best = (key, d)
    return best[1] if best else None


def compute(rows, snaps, today):
    """rows: [{repo, slug, stars}] -> (ready, rows with d7/d30 added, baseline dates {7:date|None,30:date|None})."""
    base = {w: pick_baseline(snaps, today, w) for w in WINDOWS}
    out = []
    for r in rows:
        x = dict(r)
        for w in WINDOWS:
            b = snaps[base[w]].get(str(r['repo']).lower()) if base[w] else None
            s = b.get('stars') if b else None
            x['d%d' % w] = (r['stars'] - s) if isinstance(s, (int, float)) else None
        out.append(x)
    ready = any(x['d7'] is not None for x in out)
    return ready, out, base


def rank_rows(rows, top_n=TOP_N):
    """Adds 'rank' (1..top_n or None) to each row (in place) and returns the ranked rows in rank order."""
    for r in rows: r['rank'] = None
    pos = [r for r in rows if r['d7'] is not None and r['d7'] > 0]
    pos.sort(key=lambda r: (-r['d7'], -(r['d30'] if r['d30'] is not None else float('-inf')), -r['stars'], str(r['repo']).lower()))
    for i, r in enumerate(pos[:top_n], 1): r['rank'] = i
    return pos[:top_n]


DAILY_TOP = 30
DAILY_AGE = (1, 2)


def daily_top(rows, snaps, today, top_n=DAILY_TOP):
    """Daily growth: stars_now - stars at the snapshot 1 day ago (2 days accepted when yesterday is missing).
    -> (baseline date | None, [{slug, d1}] best first). Only repos that gained stars are listed; no baseline => (None, [])."""
    base = None
    for d in snaps:
        age = (today - d).days
        if DAILY_AGE[0] <= age <= DAILY_AGE[1] and (base is None or age < (today - base).days): base = d
    if base is None: return None, []
    out = []
    for r in rows:
        b = snaps[base].get(str(r['repo']).lower())
        s = b.get('stars') if b else None
        if isinstance(s, (int, float)) and r['stars'] - s > 0:
            out.append({'slug': r['slug'], 'd1': r['stars'] - s, '_stars': r['stars'], '_repo': str(r['repo']).lower()})
    out.sort(key=lambda x: (-x['d1'], -x['_stars'], x['_repo']))
    return base, [{'slug': x['slug'], 'd1': x['d1']} for x in out[:top_n]]


def has_badge(d7, rank, stars):
    return rank is not None and d7 is not None and d7 >= max(BADGE_MIN_D7, BADGE_PCT * stars)


def trending_doc(ranked, ready, gen, snaps, base, github, today, daily=None):
    """The trending.json / trending-ai.json document."""
    used = ['stars_history']
    if github.get('enabled') and github.get('ok'): used.append('github_trending')
    doc = {
        'ready': ready, 'generated_at': gen, 'window_days': {'d7': 7, 'd30': 30},
        'items': [{'slug': r['slug'], 'd7': r['d7'], 'd30': r['d30'], 'rank': r['rank']} for r in ranked],
        'badges': sum(1 for r in ranked if has_badge(r['d7'], r['rank'], r['stars'])),
        'sources_used': used,
        'snapshot_dates': sorted(d.isoformat() for d in snaps),
        'baseline_dates': {str(w): (base[w].isoformat() if base[w] else None) for w in WINDOWS},
        'github_trending': github,
    }
    if daily is not None:
        doc['daily'] = {'ready': daily[0] is not None, 'baseline': daily[0].isoformat() if daily[0] else None, 'items': daily[1]}
    return doc


# ------------------------------------------------------------------ github.com/trending (opt-in)
def disabled_github():
    return {'enabled': False, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []}


_ARTICLE = re.compile(r'<article\b[^>]*>(.*?)</article>', re.S | re.I)
_H2LINK = re.compile(r'<h2\b[^>]*>.*?<a\b[^>]*?href="/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"', re.S | re.I)


def parse_trending_html(text):
    """Tolerant: repo names from the h2 link of each <article> row. Unknown layout => []. Never raises."""
    out, seen = [], set()
    try:
        for art in _ARTICLE.findall(text or ''):
            m = _H2LINK.search(art)
            if not m: continue
            o, r = _html.unescape(m.group(1)), _html.unescape(m.group(2))
            if o in ('.', '..', 'sponsors', 'login', 'features') or r in ('.', '..'): continue
            n = '%s/%s' % (o, r)
            if n.lower() in seen: continue
            seen.add(n.lower()); out.append(n)
    except Exception:
        return []
    return out


def _fetch_text(url, opener):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    with opener(req, timeout=30) as f:
        return f.read().decode('utf-8', errors='replace')


def get_github_trending(cache_path=None, opener=urllib.request.urlopen, now=None, log=print, sleep=time.sleep):
    """Opt-in only. -> {'enabled':True,'ok':bool,'fetched_at':iso|None,'daily':[...],'weekly':[...], 'dropped_forbidden_word':n?}.
    A cache younger than CACHE_HOURS is reused (no request). Any failure => ok False and empty lists, never an exception."""
    res = {'enabled': True, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []}
    try:
        now = now or time.time()
        if cache_path:
            try:
                c = json.loads(pathlib.Path(cache_path).read_text(encoding='utf-8'))
                if c.get('ok') and now - c.get('fetched_ts', 0) < CACHE_HOURS * 3600:
                    log('github trending: using cache')
                    return {k: c[k] for k in ('enabled', 'ok', 'fetched_at', 'daily', 'weekly')}
            except Exception:
                pass
        dropped = 0
        budget = 2                                       # hard cap: 2 HTTP requests per call; a retry spends from the same budget
        got = {}
        for key, url in GH_TRENDING.items():
            text = None
            while budget > 0 and text is None:
                budget -= 1
                try:
                    text = _fetch_text(url, opener)
                except Exception as e:
                    log('github trending %s request failed: %s' % (key, type(e).__name__))
                    if budget > 0: sleep(3)
            if text is None:                             # failure: continue the build without any github trending data
                return {'enabled': True, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []}
            names = parse_trending_html(text)
            keep = [n for n in names if not FORBIDDEN.search(n)]
            dropped += len(names) - len(keep)
            got[key] = keep
        res.update(got)
        if not (res['daily'] or res['weekly']):
            log('github trending: page parsed to zero repos (layout changed?)')
            return {'enabled': True, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []}
        res['ok'] = True
        res['fetched_at'] = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        if dropped: res['dropped_forbidden_word'] = dropped
        if cache_path:
            p = pathlib.Path(cache_path); p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(dict(res, fetched_ts=now)), encoding='utf-8')
        return res
    except Exception as e:                               # belt and braces: never break the build
        log('github trending failed: %s' % type(e).__name__)
        return {'enabled': True, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []}


# ------------------------------------------------------------------ candidates file
def read_candidates(path):
    """data/trending_candidates.txt: 'owner/repo<TAB>github_trending:daily,weekly' -> {name: [tags]}; '#' lines ignored."""
    out = {}
    p = pathlib.Path(path)
    if not p.exists(): return out
    for line in p.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        name, _, tag = line.partition('\t')
        if '/' not in name: continue
        tags = out.setdefault(name.strip(), [])
        for t in (tag.strip() or 'github_trending').split(','):
            if t and t not in tags: tags.append(t)
    return out


def write_candidates(path, existing, github):
    """Union of the old file and this fetch (source tag github_trending:<daily|weekly>). Returns the merged dict."""
    merged = {k: list(v) for k, v in existing.items()}
    lower = {k.lower(): k for k in merged}
    for key in ('daily', 'weekly'):
        for n in github.get(key) or []:
            k = lower.get(n.lower())
            if k is None:
                k = n; merged[k] = []; lower[n.lower()] = k
            tag = 'github_trending:' + key
            if tag not in merged[k]: merged[k].append(tag)
    p = pathlib.Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    lines = ['# written by the builders when --with-github-trending is used; names only, curated like every other candidate']
    for k in sorted(merged, key=str.lower):
        lines.append('%s\t%s' % (k, ','.join(merged[k]) or 'github_trending'))
    p.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    return merged
