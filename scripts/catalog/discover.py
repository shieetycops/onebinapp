"""Daily discovery of NEW desktop-app candidates, from the same sources as the round-3 pool (scripts/18_draw_round3.py):
  * komi cached data   (refreshed by `git pull` in CI; read by build_catalog.candidates() directly, nothing to do here)
  * Homebrew cask list (https://formulae.brew.sh/api/cask.json: GitHub repos found in url / homepage)
  * GitHub topic search: electron, tauri, desktop-app, qt, gtk, flutter-desktop, stars >= 100, not fork, not archived
Output: data/discovered.txt, lines 'owner/repo<TAB>source<TAB>first_seen_date' (append only, never edits data/round3 or seen_repos.txt).
build_catalog.py adds these names to its candidates and runs the SAME curation (C1-C4b + installer requirement); who got in or out
is written to the changelog.  At most --max-new new names per run (highest stars first) to protect the API budget.
Run:  python -I scripts/catalog/discover.py [--max-new 150] [--pages 3] [--offline]      Token: GH_TOKEN / ~/.gh_token (never written)."""
import sys, re, json, time, pathlib, argparse, datetime, urllib.request, urllib.error, urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
ROOT = HERE.parent.parent
DATA = ROOT / 'data'
TOPICS = ('electron', 'tauri', 'desktop-app', 'qt', 'gtk', 'flutter-desktop')
CASK_URL = 'https://formulae.brew.sh/api/cask.json'
GH = re.compile(r'github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)')
NAME_OK = re.compile(r'^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$')


def parse_cask(text):
    """Homebrew cask JSON -> set of 'owner/repo' found in url/homepage."""
    out = set()
    for c in json.loads(text):
        for k in ('url', 'homepage'):
            m = GH.search((c.get(k) if isinstance(c, dict) else '') or '')
            if m:
                n = m.group(1) + '/' + re.sub(r'\.git$', '', m.group(2))
                if NAME_OK.match(n): out.add(n)
    return out


def parse_search(text):
    """GitHub search response -> [(full_name, stars)] (only well-formed names)."""
    try: items = json.loads(text).get('items', [])
    except Exception: return []
    return [(it['full_name'], it.get('stargazers_count') or 0) for it in items if isinstance(it, dict) and NAME_OK.match(it.get('full_name') or '')]


def known_names():
    """Everything build_catalog.candidates() already looks at, plus what discovery found before (case-insensitive)."""
    import build_catalog as B           # hash-verifies picker/classifier (same guard as the builder)
    k = {n.lower() for n in B.candidates()}
    k |= set(B.discovered_map())
    return k


def select_new(found, known, max_new):
    """found: {name: (stars, source)} -> list of (name, source) not known, highest stars first, capped."""
    fresh = [(n, st, src) for n, (st, src) in found.items() if n.lower() not in known]
    fresh.sort(key=lambda x: (-x[1], x[0].lower()))
    return [(n, src) for n, _, src in fresh[:max_new]]


def http_get(url, token=None, timeout=60):
    h = {'User-Agent': 'catalog-discover', 'Accept': 'application/vnd.github+json' if token else 'application/json'}
    if token: h['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as f: return f.status, f.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def collect(token, pages, fetch=http_get, sleep=time.sleep):
    """-> (found {name: (stars, source)}, report).  A failing source is logged and skipped, never fatal."""
    found, rep = {}, {'cask': None, 'topics': {}}
    try:
        st, body = fetch(CASK_URL)
        if st == 200:
            names = parse_cask(body); rep['cask'] = len(names)
            for n in names: found.setdefault(n, (0, 'cask'))
        else: rep['cask'] = 'http %s' % st
    except Exception as e:
        rep['cask'] = 'error %s' % type(e).__name__
    for t in TOPICS:
        got = 0
        for pg in range(1, pages + 1):
            q = 'topic:%s stars:>=100 fork:false archived:false' % t
            url = 'https://api.github.com/search/repositories?q=%s&sort=updated&order=desc&per_page=100&page=%d' % (urllib.parse.quote(q), pg)
            try:
                st, body = fetch(url, token)
            except Exception as e:
                rep['topics'][t] = 'error %s' % type(e).__name__; break
            if st != 200:
                rep['topics'][t] = 'http %s' % st; break
            items = parse_search(body)
            for n, stars in items:
                prev = found.get(n)
                if prev is None or prev[1] == 'cask': found[n] = (stars, 'gh_topic:' + t)
            got += len(items)
            sleep(2.5)                                       # search API: 30 requests per minute
            if len(items) < 100: break
        rep['topics'].setdefault(t, got)
    return found, rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-new', type=int, default=150)
    ap.add_argument('--pages', type=int, default=3)
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--out', default=str(DATA / 'discovered.txt'))
    a = ap.parse_args()
    if a.offline:
        print('offline: nothing to discover'); return 0
    import build_catalog as B
    token = B.load_token()
    if not token: print('no token (GH_TOKEN or ~/.gh_token)', file=sys.stderr); return 2
    found, rep = collect(token, a.pages)
    new = select_new(found, known_names(), a.max_new)
    today = datetime.date.today().isoformat()
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if new:
        with open(out, 'a', encoding='utf-8', newline='\n') as f:
            for n, src in new: f.write('%s\t%s\t%s\n' % (n, src, today))
    print(json.dumps({'sources': rep, 'found': len(found), 'new_written': len(new), 'cap': a.max_new}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
