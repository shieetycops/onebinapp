"""Round 3 draw, exactly as data/round3/LOCK.md sections 2-4. Run: python -I scripts/18_draw_round3.py
Outputs under data/round3/: search_raw/*.json, pool_info.json, raw/{repo}.meta.json, raw/{repo}.release.json,
curation_decisions.json, all_assets.json (strict-extension assets of curated repos), draw_progress.json.
Stopping depends ONLY on extension counts (never on picker output or gold)."""
import json, glob, pathlib, random, re, time, urllib.request, urllib.error, concurrent.futures as cf, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import picker_v3 as P  # only ext_kind / STRICT ext; no picking
D = HERE.parent / 'data'
R3 = D / 'round3'; RAW = R3 / 'raw'; SRAW = R3 / 'search_raw'
RAW.mkdir(exist_ok=True); SRAW.mkdir(exist_ok=True)
T = open(pathlib.Path.home() / '.gh_token').read().strip()
HDR = {'Authorization': 'Bearer ' + T, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'feasibility-study'}
BATCH, CAP, MINQ = 100, 1200, 60


def api(url, tries=4):
    for i in range(tries):
        req = urllib.request.Request(url, headers=HDR)
        try:
            with urllib.request.urlopen(req, timeout=40) as f:
                return f.status, f.read(), f.headers
        except urllib.error.HTTPError as e:
            body, h = e.read(), e.headers
            if e.code in (403, 429) and (h.get('x-ratelimit-remaining') == '0' or h.get('retry-after')):
                wait = max(5, int(h.get('x-ratelimit-reset', time.time() + 30)) - int(time.time()) + 2)
                time.sleep(min(wait, 120)); continue
            return e.code, body, h
        except Exception:
            time.sleep(2 * (i + 1))
    return 'ERR', b'', {}


seen = {l.strip().lower() for l in open(R3 / 'seen_repos.txt', encoding='utf-8') if l.strip()}
# --- komi
komi = set()
for f in glob.glob(str(D / 'ext/komi/komi-store-backend-data/cached-data/**/*.json'), recursive=True):
    for r in json.load(open(f, encoding='utf-8'))['repositories']: komi.add(r['fullName'])
# --- cask
GH = re.compile(r'github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)')
cask = set()
for c in json.load(open(D / 'ext/cask.json', encoding='utf-8')):
    for k in ('url', 'homepage'):
        m = GH.search(c.get(k) or '')
        if m: cask.add(m.group(1) + '/' + re.sub(r'\.git$', '', m.group(2)))
# --- gh_search (raw saved)
gs = set()
for t in ('electron', 'tauri', 'desktop-app', 'qt', 'gtk', 'flutter-desktop'):
    for pg in range(1, 11):
        fp = SRAW / f'{t}_{pg}.json'
        if fp.exists(): body = fp.read_bytes()
        else:
            q = f'topic:{t} stars:100..999 fork:false archived:false'
            st, body, _ = api('https://api.github.com/search/repositories?q=' + urllib.request.quote(q) + f'&sort=stars&order=desc&per_page=100&page={pg}')
            fp.write_bytes(body); time.sleep(2.5)
        try: items = json.loads(body).get('items', [])
        except Exception: items = []
        for it in items: gs.add(it['full_name'])
        if len(items) < 100: break
srcs, taken = [], set(seen)
for i, (nm, s) in enumerate((('komi', komi), ('cask', cask), ('gh_search', gs))):
    lst = sorted(x for x in s if x.lower() not in taken)
    taken.update(x.lower() for x in lst)
    random.Random(20261114 + i).shuffle(lst)
    srcs.append((nm, lst))
pool, src_of, idx = [], {}, 0
while any(len(l) > idx for _, l in srcs):
    for nm, l in srcs:
        if len(l) > idx: pool.append(l[idx]); src_of[l[idx]] = nm
    idx += 1
json.dump({'sizes_after_exclusion': {n: len(l) for n, l in srcs}, 'raw_sizes': {'komi': len(komi), 'cask': len(cask), 'gh_search': len(gs)}, 'seen': len(seen), 'pool': len(pool), 'order': pool, 'source_of': src_of}, open(R3 / 'pool_info.json', 'w'), indent=0)

TOK = re.compile(r'[a-z0-9]+')
BAD = set('library lib framework sdk boilerplate template starter plugin extension theme icons dotfiles awesome tutorial example demo driver firmware kernel compiler linter backend'.split())
GUI = {'desktop-app', 'electron', 'tauri', 'gui', 'qt', 'gtk', 'desktop', 'flutter-desktop'}


def curate(m):
    why = []
    if m.get('fork') or m.get('archived') or m.get('disabled'): why.append('C1')
    if (m.get('stargazers_count') or 0) < 100: why.append('C2')
    if not (m.get('description') or '').strip(): why.append('C3')
    topics = [t.lower() for t in m.get('topics') or []]
    toks = set(TOK.findall((m.get('name') or '').lower())) | set(TOK.findall((m.get('description') or '').lower())) | {x for t in topics for x in TOK.findall(t)}
    hit = sorted(toks & BAD)
    if hit: why.append('C4a:' + ','.join(hit))
    if ('cli' in topics or 'command-line' in topics) and not (set(topics) & GUI): why.append('C4b')
    return why


def one(name):
    key = name.replace('/', '__')
    mp = RAW / f'{key}.meta.json'
    if mp.exists(): st, body = 200, mp.read_bytes()
    else:
        st, body, _ = api(f'https://api.github.com/repos/{name}'); mp.write_bytes(body)
    if st != 200: return name, {'curated': False, 'why': [f'meta_http_{st}']}, None
    m = json.loads(body); why = curate(m)
    if why: return name, {'curated': False, 'why': why, 'stars': m.get('stargazers_count')}, None
    rp = RAW / f'{key}.release.json'
    if rp.exists(): rst, rbody = 200, rp.read_bytes()
    else:
        rst, rbody, _ = api(f'https://api.github.com/repos/{name}/releases/latest'); rp.write_bytes(rbody)
    assets = []
    if rst == 200:
        j = json.loads(rbody)
        for a in j.get('assets', []):
            k = P.ext_kind(a['name'])
            if k: assets.append({'repo': name, 'tag': j.get('tag_name'), 'asset_name': a['name'], 'size': a['size'], 'url': a['browser_download_url'], 'ext': k, 'source': src_of[name]})
    return name, {'curated': True, 'why': [], 'stars': m.get('stargazers_count'), 'release_http': rst, 'n_strict_assets': len(assets)}, assets


OSX = {'windows': ('exe', 'msi', 'msix', 'appx'), 'macos': ('dmg', 'pkg'), 'linux': ('appimage',)}
decisions, assets, fetched, progress = {}, [], 0, []
while fetched < min(CAP, len(pool)):
    batch = pool[fetched:fetched + BATCH]
    with cf.ThreadPoolExecutor(6) as e: res = list(e.map(one, batch))
    for name, dec, a in res:
        decisions[name] = dict(dec, source=src_of[name])
        if a: assets.extend(a)
    fetched += len(batch)
    qual = {o: len({a['repo'] for a in assets if a['ext'] in ex}) for o, ex in OSX.items()}
    progress.append({'fetched': fetched, 'curated': sum(d['curated'] for d in decisions.values()), 'qualifying': qual})
    print(progress[-1], flush=True)
    if all(v >= MINQ for v in qual.values()): break
stopped = 'rule' if all(v >= MINQ for v in progress[-1]['qualifying'].values()) else ('cap' if fetched >= CAP else 'pool_exhausted')
json.dump(decisions, open(R3 / 'curation_decisions.json', 'w'), indent=0)
json.dump(assets, open(R3 / 'all_assets.json', 'w', encoding='utf-8'), indent=0)
json.dump({'stopped_by': stopped, 'progress': progress}, open(R3 / 'draw_progress.json', 'w'), indent=1)
print('stopped_by', stopped, 'fetched', fetched, 'assets', len(assets))
