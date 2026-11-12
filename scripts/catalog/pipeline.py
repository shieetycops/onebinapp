"""Daily-pipeline helpers shared by build_catalog.py and build_ai.py (stdlib only, no network).

* classify_freshness: per repo, decide fresh / stale (previous good data reused) / expired / missing.
* guard: refuse to publish when too many repos are not fresh (the "Katalog diperbarui" date must not lie).
* changelog: diff of catalog membership between two builds with a reason for every change, persisted in
  data/changelog/<section>.jsonl (history) and data/changelog/<section>-state.json (previous membership).
"""
import json, pathlib, time, datetime

MAX_STALE_DAYS = 7          # a repo that cannot be fetched keeps its previous data for at most this long
MAX_NOT_FRESH_FRACTION = 0.20   # more than this share of repos not fresh => the run fails (nothing is deployed)
CHANGELOG_KEEP = 60         # entries kept in the published changelog JSON


def classify_freshness(names, fetched_at_of, now_ts, max_age_h, max_stale_days=MAX_STALE_DAYS):
    """fetched_at_of(name) -> epoch seconds or None (no cached data).
    -> dict(fresh=[...], stale=[(name, age_days)], expired=[(name, age_days)], missing=[...])"""
    out = {'fresh': [], 'stale': [], 'expired': [], 'missing': []}
    for n in names:
        t = fetched_at_of(n)
        if t is None:
            out['missing'].append(n); continue
        age_h = (now_ts - t) / 3600.0
        if age_h <= max_age_h: out['fresh'].append(n)
        elif age_h <= max_stale_days * 24: out['stale'].append((n, round(age_h / 24.0, 2)))
        else: out['expired'].append((n, round(age_h / 24.0, 2)))
    return out


def guard(total, fr, max_fraction=MAX_NOT_FRESH_FRACTION):
    """-> (ok, not_fresh_count, fraction).  Stale, expired and missing all count as not fresh."""
    bad = len(fr['stale']) + len(fr['expired']) + len(fr['missing'])
    frac = bad / total if total else 0.0
    return frac <= max_fraction, bad, round(frac, 4)


def freshness_stats(fr, max_stale_days=MAX_STALE_DAYS):
    return {'fresh': len(fr['fresh']), 'stale_reused': len(fr['stale']), 'stale_expired': len(fr['expired']),
            'missing': len(fr['missing']), 'max_stale_days': max_stale_days,
            'stale_repos': [{'repo': n, 'age_days': a} for n, a in sorted(fr['stale'], key=lambda x: -x[1])[:25]]}


# ------------------------------------------------------------------ changelog
def _read(p, default):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
    except Exception:
        return default


def diff_membership(prev, cur, reasons, sources=None, default_reason='no_longer_a_candidate'):
    """prev/cur: {repo(lower): {'repo': 'Owner/Name', 'stars': n}}.  reasons: {repo(lower): code} for candidates NOT in cur.
    sources: {repo(lower): source tag} for new entries.  -> (added, removed)"""
    sources = sources or {}
    added = [{'repo': cur[k]['repo'], 'stars': cur[k].get('stars'), 'source': sources.get(k)} for k in sorted(cur) if k not in prev]
    removed = [{'repo': prev[k]['repo'], 'reason': reasons.get(k, default_reason)} for k in sorted(prev) if k not in cur]
    return added, removed


def record_changelog(dirpath, section, date, cur, reasons, sources=None, extra=None, write=True, default_reason='no_longer_a_candidate'):
    """Compare `cur` with the persisted previous membership, append one changelog line, replace the state.
    First run (no state) is recorded as a baseline, not as N additions.  -> the entry written."""
    d = pathlib.Path(dirpath)
    state_p, log_p = d / (section + '-state.json'), d / (section + '.jsonl')
    st = _read(state_p, None)
    # a re-run on the same day diffs against the membership at the START of that day (so the day's entry is not wiped by an empty diff)
    if st is not None and st.get('date') == date and st.get('baseline'): st = None      # re-run on the baseline day stays a baseline
    prev = None if st is None else {'entries': (st.get('base_entries') if st.get('date') == date and 'base_entries' in st else st.get('entries', {}))}
    if prev is None:
        entry = {'date': date, 'baseline': True, 'count': len(cur), 'added': [], 'removed': []}
    else:
        added, removed = diff_membership(prev.get('entries', {}), cur, reasons, sources, default_reason)
        entry = {'date': date, 'baseline': False, 'count': len(cur), 'added': added, 'removed': removed}
    if extra: entry.update(extra)
    if write:
        d.mkdir(parents=True, exist_ok=True)
        lines = []
        if log_p.exists():
            lines = [l for l in log_p.read_text(encoding='utf-8').splitlines() if l.strip()]
            lines = [l for l in lines if _read_line(l).get('date') != date]       # one entry per day: a re-run replaces it
        lines.append(json.dumps(entry, ensure_ascii=False, separators=(',', ':')))
        log_p.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
        base = prev['entries'] if prev is not None else cur
        state_p.write_text(json.dumps({'date': date, 'entries': cur, 'base_entries': base, 'baseline': bool(entry.get('baseline'))}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')
    return entry


def _read_line(l):
    try: return json.loads(l)
    except Exception: return {}


def published_changelog(dirpath, section, keep=CHANGELOG_KEEP):
    p = pathlib.Path(dirpath) / (section + '.jsonl')
    if not p.exists(): return []
    rows = [_read_line(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
    return [r for r in rows if r][-keep:][::-1]


def update_meta(out_dir, key, generated_at):
    """site/public/data/meta.json {desktop: iso, ai: iso}: the footer reads "Katalog diperbarui" from here."""
    p = pathlib.Path(out_dir) / 'meta.json'
    m = _read(p, {})
    if not isinstance(m, dict): m = {}
    m[key] = generated_at
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, separators=(',', ':')), encoding='utf-8', newline='\n')
