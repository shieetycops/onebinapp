"""Draw the clean sample exactly as data/clean/DRAW_RULE.md says. Outputs under data/clean/:
raw/*.json (+headers), all_assets.json, labels_todo.csv, pool_info.json"""
import json, glob, pathlib, random, csv, urllib.request, urllib.error, concurrent.futures as cf, datetime
D = pathlib.Path(__file__).resolve().parent.parent / 'data'
C = D / 'clean'; RAW = C / 'raw'; RAW.mkdir(parents=True, exist_ok=True)
T = open(pathlib.Path.home() / '.gh_token').read().strip()
seen = set()
for p in ('repos.json', 'repos_all_candidates.json'):
    for r in json.load(open(D / p, encoding='utf-8')):
        seen.add(r['repo'] if 'repo' in r else r.get('full_name') or r.get('fullName'))
ex = json.load(open(D / 'excluded.json', encoding='utf-8'))
if isinstance(ex, dict):
    for v in ex.values():
        if isinstance(v, list): seen.update(x if isinstance(x, str) else x.get('repo') for x in v)
        elif isinstance(v, dict): seen.update(v.keys())
cur = json.load(open(D / 'curation.json', encoding='utf-8')); seen.update(cur.get('denied', {}).keys()); seen.update(cur.get('refilled', []))
seen.update(json.load(open(D / 'curation_extra_deny.json', encoding='utf-8')).keys())
seen.discard(None)
pool = set()
for f in glob.glob(str(D / 'ext/komi/komi-store-backend-data/cached-data/**/*.json'), recursive=True):
    for r in json.load(open(f, encoding='utf-8'))['repositories']: pool.add(r['fullName'])
lower_seen = {s.lower() for s in seen}
pool = sorted(p for p in pool if p.lower() not in lower_seen)
rnd = random.Random(20261112); rnd.shuffle(pool)
chosen = pool[:250]
json.dump({'komi_unique': len(pool) + len(lower_seen & {p.lower() for p in pool}), 'seen_repos': len(seen), 'pool_after_exclusion': len(pool), 'chosen_repos': chosen}, open(C / 'pool_info.json', 'w'), indent=1)


def one(name):
    key = name.replace('/', '__')
    req = urllib.request.Request(f'https://api.github.com/repos/{name}/releases/latest', headers={'Authorization': 'Bearer ' + T, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'feasibility-study'})
    try:
        with urllib.request.urlopen(req, timeout=30) as f: st, body, hdr = f.status, f.read(), f.headers
    except urllib.error.HTTPError as e: st, body, hdr = e.code, e.read(), e.headers
    except Exception as e: return name, 'ERR', None
    (RAW / f'{key}.json').write_bytes(body)
    (RAW / f'{key}.headers.txt').write_text(''.join(f'{k}: {v}\n' for k, v in hdr.items()), encoding='utf-8')
    return name, st, body


with cf.ThreadPoolExecutor(6) as e: res = list(e.map(one, chosen))
rows = []
status = {}
for name, st, body in res:
    status[str(st)] = status.get(str(st), 0) + 1
    if st != 200: continue
    j = json.loads(body)
    for a in j.get('assets', []): rows.append({'repo': name, 'tag': j.get('tag_name'), 'asset_name': a['name'], 'size': a['size'], 'url': a['browser_download_url']})
json.dump(rows, open(C / 'all_assets.json', 'w', encoding='utf-8'), indent=0)
rnd2 = random.Random(20261113); rnd2.shuffle(rows)
per, pick = {}, []
for r in rows:
    if per.get(r['repo'], 0) >= 3: continue
    per[r['repo']] = per.get(r['repo'], 0) + 1; pick.append(r)
    if len(pick) == 400: break
with open(C / 'labels_todo.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['repo', 'asset_name', 'size', 'OS', 'arch', 'type'])
    for r in pick: w.writerow([r['repo'], r['asset_name'], r['size'], '', '', ''])
print('status', status, '| repos with assets', len({r['repo'] for r in rows}), '| assets total', len(rows), '| sample', len(pick), 'repos in sample', len(per), '| pool', len(pool), 'seen', len(seen))
