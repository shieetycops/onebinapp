"""Extra fetch for the "Cara pakai" section: plugin components only (commands/, agents/, hooks/hooks.json + short frontmatter).
Reads/writes ONLY data/catalog_cache_ai/usage/<slug>.json. Included entries only (types contain 'plugin'). Repo text is data: it is
only stored, never executed. Run:  python -I scripts/catalog/usage_fetch.py [--limit N]   (needs ~/.gh_token or GH_TOKEN)."""
import sys, json, time, pathlib, argparse

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import build_ai as A      # noqa: E402
import build_catalog as B  # noqa: E402

UCACHE = A.CACHE / 'usage'
MAX_FM = 8          # frontmatter files per folder
BATCH = 5


def plugin_base(M, repo):
    """Folder (repo-relative, '' = root) of the plugin that the install command installs, or None when it is not inside this repo."""
    mk = (M.get('marketplaces') or {}).get('.claude-plugin/marketplace.json')
    if mk:
        pl = [p for p in (mk.get('plugins') or []) if isinstance(p, dict) and isinstance(p.get('name'), str) and p['name']]
        if not pl: return None
        s = pl[0].get('source')
        if isinstance(s, dict):
            return '' if s.get('source') == 'github' and str(s.get('repo', '')).lower() == repo.lower() else None
        if isinstance(s, str):
            s = s.strip()
            if s in ('.', './', ''): return ''
            if s.startswith('./') and '..' not in s: return s[2:].strip('/')
        return None
    return ''


def _p(base, rel): return (base + '/' + rel) if base else rel


def stage1(fetcher, items):
    parts = []
    for i, (slug, repo, base) in enumerate(items):
        o, n = repo.split('/')
        parts.append('r%d: repository(owner:%s,name:%s){ c: object(expression:%s){...on Tree{entries{name type}}} a: object(expression:%s){...on Tree{entries{name type}}} '
                     'h: object(expression:%s){...on Blob{text isTruncated}} p: object(expression:%s){...on Blob{text isTruncated}} }' % (
                         i, json.dumps(o), json.dumps(n), json.dumps('HEAD:' + _p(base, 'commands')), json.dumps('HEAD:' + _p(base, 'agents')),
                         json.dumps('HEAD:' + _p(base, 'hooks/hooks.json')), json.dumps('HEAD:' + _p(base, '.claude-plugin/plugin.json'))))
    data, _ = fetcher.with_retry('query { rateLimit { cost remaining resetAt } ' + ' '.join(parts) + ' }')
    return [data.get('r%d' % i) for i in range(len(items))]


def stage2(fetcher, jobs):
    """jobs: [(repo, [paths])] -> [{path: text}]"""
    parts = []
    for i, (repo, paths) in enumerate(jobs):
        o, n = repo.split('/')
        body = ' '.join('f%d: object(expression:%s){...on Blob{text}}' % (j, json.dumps('HEAD:' + p)) for j, p in enumerate(paths))
        parts.append('r%d: repository(owner:%s,name:%s){ %s }' % (i, json.dumps(o), json.dumps(n), body))
    data, _ = fetcher.with_retry('query { rateLimit { cost remaining resetAt } ' + ' '.join(parts) + ' }')
    out = []
    for i, (repo, paths) in enumerate(jobs):
        r = data.get('r%d' % i) or {}
        out.append({p: ((r.get('f%d' % j) or {}).get('text') or '')[:1500] for j, p in enumerate(paths)})
    return out


def entries(tree):
    return [(e['name'], e['type']) for e in (tree or {}).get('entries') or []]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    token = B.load_token()
    if not token: print('no token'); return 2
    fetcher = A.AIFetcher(token)
    UCACHE.mkdir(parents=True, exist_ok=True)
    now = time.time()
    import datetime
    cat = json.loads((B.OUT / 'catalog-ai.json').read_text(encoding='utf-8'))
    items = []
    for e in cat['entries']:
        if 'plugin' not in e['types']: continue
        j = A.read_json(A.repo_cache(e['repo']))
        if not j or not j.get('rec'): continue
        M = A.CU.parse_manifests(j['rec']['texts'], None, {})
        base = plugin_base(M, e['repo'])
        if base is None:
            A_write(e['slug'], {'fetched_at': now, 'base': None}); continue
        items.append((e['slug'], e['repo'], base))
    if a.limit: items = items[:a.limit]
    print('plugin entries to fetch:', len(items))
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        res = stage1(fetcher, chunk)
        jobs, meta = [], []
        for (slug, repo, base), r in zip(chunk, res):
            r = r or {}
            cmd, ag = entries(r.get('c')), entries(r.get('a'))
            hooks = (r.get('h') or {}).get('text') if r.get('h') and not (r.get('h') or {}).get('isTruncated') else None
            pj = (r.get('p') or {}).get('text') if base and r.get('p') else None
            rec = {'fetched_at': now, 'base': base, 'commands': [n for n, t in cmd if t == 'blob'][:60], 'agents': [n for n, t in ag if t == 'blob'][:60],
                   'hooks_json': hooks, 'plugin_json': pj, 'fm': {}}
            paths = [_p(base, 'commands/' + n) for n in rec['commands'][:MAX_FM] if n.endswith('.md')] + \
                    [_p(base, 'agents/' + n) for n in rec['agents'][:MAX_FM] if n.endswith('.md')]
            meta.append((slug, repo, rec, paths))
            if paths: jobs.append((repo, paths))
        texts = stage2(fetcher, jobs) if jobs else []
        k = 0
        for slug, repo, rec, paths in meta:
            if paths: rec['fm'] = texts[k]; k += 1
            A_write(slug, rec)
        print('  %d/%d' % (min(i + BATCH, len(items)), len(items)))


def A_write(slug, rec):
    B.atomic_write(UCACHE / (slug + '.json'), B.jdump(rec))


if __name__ == '__main__':
    sys.exit(main())
