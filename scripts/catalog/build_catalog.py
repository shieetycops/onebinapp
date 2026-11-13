"""Catalog builder (SPEC.md section 1). One command, idempotent:  python -I scripts/catalog/build_catalog.py
Options: --limit N  --only owner/repo  --max-age-hours H (default 20)  --fetch-only  --batch N (default 25)
         --history-dir DIR (star snapshots; default data/history)  --with-github-trending (OPT-IN, default off; see trending.py)
Exit codes: 0 complete, 2 refused (hash mismatch / no token), 3 (only with --strict) some candidates unfetched, 4 guard: too many repos not fresh (nothing written).
Daily mode (default): repo metadata by light GraphQL, releases by REST with ETag (releases_rest.py; --releases graphql = old behaviour);
a repo that cannot be fetched keeps its previous cached data for --max-stale-days (7) and is counted in stats.freshness.

Phases: (1) fetch GraphQL batches into data/catalog_cache/repos/*.json (atomic, resumable, one repo per file);
(2) build: stream the cache one repo at a time, curate, pick, write apps/<slug>.json; keep only cards in memory.

Android rule (separate from the evaluated picker, UNEVALUATED, name only): candidates = *.apk assets whose name has no
helper token (uninstall/updater/debug/runtime/driver/cli/...); one candidate -> pick it; several -> pick only if exactly one has
arch 'universal' (classifier tokens) else exactly one without any arch token; otherwise stay silent (null).
Platform of an asset with a strict installer extension comes from the extension (exe/msi/msix/appx=windows, dmg/pkg=macos,
AppImage=linux, apk=android); the classifier OS is only a label for other assets.
Token: env GH_TOKEN, else ~/.gh_token. It is never printed or written."""
import sys, os, re, json, time, glob, hashlib, pathlib, argparse, datetime, urllib.request, urllib.error

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent
ROOT = SCRIPTS.parent
DATA = ROOT / 'data'
CACHE = DATA / 'catalog_cache'
REPOS_CACHE = CACHE / 'repos'
COST_LOG = CACHE / 'cost_log.jsonl'
OUT = ROOT / 'site' / 'public' / 'data'
HIST = DATA / 'history'
CHANGELOG = DATA / 'changelog'

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def sha256_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def verify_hashes():
    """Refuse to run (before importing picker/classifier) unless both match data/round3/hashes.txt."""
    want = {}
    for line in (DATA / 'round3' / 'hashes.txt').read_text(encoding='utf-8').splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2: want[parts[1].lstrip('*').replace('\\', '/')] = parts[0]
    got = {}
    for rel in ('scripts/picker_v3.py', 'scripts/classifier_v3.py'):
        if want.get(rel) is None:
            raise SystemExit('hashes.txt has no entry for ' + rel)
        got[rel] = sha256_file(ROOT / rel)
        if got[rel] != want[rel]:
            print('REFUSING: sha256 mismatch for', rel, file=sys.stderr)
            raise SystemExit(2)
    return got['scripts/picker_v3.py']


PICKER_SHA = verify_hashes()
sys.path[:0] = [str(HERE), str(SCRIPTS)]
import picker_v3 as P          # noqa: E402  (unchanged, hash-verified)
import classifier_v3 as CL     # noqa: E402
import curation as CUR         # noqa: E402
import trending as TR          # noqa: E402
import categories as CAT       # noqa: E402
import pipeline as PL         # noqa: E402
import releases_rest as RR    # noqa: E402

CELLS = [('windows', 'x64'), ('windows', 'arm64'), ('macos', 'arm64'), ('macos', 'x64'), ('linux', 'x64'), ('linux', 'arm64')]
EXT_OS = {'exe': 'windows', 'msi': 'windows', 'msix': 'windows', 'appx': 'windows', 'dmg': 'macos', 'pkg': 'macos', 'appimage': 'linux', 'apk': 'android'}
PLATFORM_ORDER = ['windows', 'macos', 'linux', 'android']
SIDECAR = re.compile(r'(\.(sha256|sha256sum|sha512|sig|minisig|asc)$|sha256sums?|checksums?)', re.I)
APK_HELPER = re.compile(r'(^|[^a-z0-9])(uninstall(er)?|updater?|debug|runtime|driver|cli|legacy)([^a-z0-9]|$)')
NOTES_MAX = 4000
MAX_RELEASES = 15

GQL_FIELDS = '''
fragment F on Repository {
  databaseId nameWithOwner description stargazerCount forkCount isFork isArchived isDisabled
  owner { login avatarUrl }
  repositoryTopics(first: 20) { nodes { topic { name } } }
  licenseInfo { spdxId }
  homepageUrl pushedAt
  latestRelease { ...R }
  releases(first: @REL@, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { ...R } }
}
fragment R on Release {
  tagName name isPrerelease isDraft publishedAt description url
  releaseAssets(first: 100) { nodes { name size downloadCount downloadUrl updatedAt } }
}
'''

GQL_LIGHT = GQL_FIELDS.split('fragment R on Release')[0].replace('latestRelease { ...R }', 'latestRelease { tagName }').replace(
    '  releases(first: @REL@, orderBy: {field: CREATED_AT, direction: DESC}) { nodes { ...R } }\n', '')


# ---------------------------------------------------------------- io helpers
def atomic_write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp%d' % os.getpid())
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)


def jdump(obj, indent=None):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':') if indent is None else None, indent=indent)


def load_token():
    t = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not t:
        p = pathlib.Path.home() / '.gh_token'
        if p.exists(): t = p.read_text(encoding='utf-8').strip()
    return t or None


# ---------------------------------------------------------------- candidates
def candidates():
    """Union, case-insensitive, stable order: round-3 drawn first, then seen, komi, extra."""
    seen, out = set(), []

    def add(n):
        n = (n or '').strip()
        if '/' not in n: return
        if n.lower() in seen: return
        seen.add(n.lower()); out.append(n)

    pool = json.loads((DATA / 'round3' / 'pool_info.json').read_text(encoding='utf-8'))['order'][:300]
    for n in pool: add(n)
    for l in (DATA / 'round3' / 'seen_repos.txt').read_text(encoding='utf-8').splitlines(): add(l)
    komi = set()
    for f in glob.glob(str(DATA / 'ext/komi/komi-store-backend-data/cached-data/**/*.json'), recursive=True):
        for r in json.loads(pathlib.Path(f).read_text(encoding='utf-8'))['repositories']:
            komi.add(r['fullName'])
    for n in sorted(komi, key=str.lower): add(n)
    for n in discovered_map().values(): add(n[0])
    extra = DATA / 'catalog_extra.txt'
    if extra.exists():
        for l in extra.read_text(encoding='utf-8').splitlines():
            if l.strip() and not l.strip().startswith('#'): add(l)
    return out


def discovered_map(path=None):
    """data/discovered.txt (written by discover.py): 'owner/repo<TAB>source<TAB>first_seen_date' -> {lower: (name, source, date)}."""
    p = pathlib.Path(path) if path else DATA / 'discovered.txt'
    out = {}
    if p.exists():
        for l in p.read_text(encoding='utf-8').splitlines():
            f = l.split('\t')
            if len(f) >= 2 and '/' in f[0] and not f[0].startswith('#'):
                out[f[0].strip().lower()] = (f[0].strip(), f[1].strip(), f[2].strip() if len(f) > 2 else '')
    return out


def cache_path(name):
    return REPOS_CACHE / (name.lower().replace('/', '__') + '.json')


def cache_fresh(name, max_age_h):
    p = cache_path(name)
    if not p.exists(): return False
    try:
        j = json.loads(p.read_text(encoding='utf-8'))
        return (time.time() - j['fetched_at']) < max_age_h * 3600
    except Exception:
        return False


# ---------------------------------------------------------------- GraphQL
class Fetcher:
    def __init__(self, token):
        self.token = token
        self.remaining = None
        self.reset_at = None
        self.session_cost = 0
        self.queries = 0
        self.rest = None            # RR.RestReleases when releases come from REST (default in daily mode)
        self.rest_failed = []
        self.rest_skip = None       # callable(name, node) -> True: curation/deny list already rejects the repo, so its releases are not requested
        self.rest_skipped = 0

    def _post(self, query):
        body = json.dumps({'query': query}).encode()
        req = urllib.request.Request('https://api.github.com/graphql', data=body, headers={
            'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json',
            'User-Agent': 'catalog-builder'})
        with urllib.request.urlopen(req, timeout=120) as f:
            return json.loads(f.read().decode('utf-8'))

    def wait_if_low(self):
        if self.remaining is not None and self.remaining < 200 and self.reset_at:
            wait = max(5, self.reset_at - time.time() + 5)
            print('rate limit low (remaining %d), sleeping %ds' % (self.remaining, wait), flush=True)
            time.sleep(wait)
            self.remaining = None

    def query_batch(self, names, rel_n=15):
        """-> dict name -> node|None (None = not found). Raises on failure of the whole call."""
        parts = []
        for i, n in enumerate(names):
            o, r = n.split('/', 1)
            parts.append('r%d: repository(owner: %s, name: %s) { ...F }' % (i, json.dumps(o), json.dumps(r)))
        q = 'query { rateLimit { cost remaining resetAt } ' + ' '.join(parts) + ' }' + (GQL_LIGHT if rel_n == 0 else GQL_FIELDS.replace('@REL@', str(rel_n)))
        resp = self._post(q)
        data = resp.get('data')
        if not data:
            raise RuntimeError('graphql no data: ' + json.dumps(resp.get('errors'))[:300])
        for e in resp.get('errors') or []:
            if e.get('type') != 'NOT_FOUND':
                if e.get('type') in ('RESOURCE_LIMITS_EXCEEDED', 'NODE_LIMIT_EXCEEDED', 'MAX_NODE_LIMIT_EXCEEDED') or 'timeout' in json.dumps(e).lower():
                    raise RuntimeError('graphql limit: ' + json.dumps(e)[:200])
        rl = data.get('rateLimit') or {}
        cost, rem = rl.get('cost'), rl.get('remaining')
        self.remaining = rem
        try:
            self.reset_at = datetime.datetime.fromisoformat(rl['resetAt'].replace('Z', '+00:00')).timestamp()
        except Exception:
            self.reset_at = time.time() + 600
        self.session_cost += cost or 0
        self.queries += 1
        with open(COST_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': int(time.time()), 'repos': len(names), 'cost': cost, 'remaining': rem}) + '\n')
        print('  batch of %d repos: cost=%s remaining=%s' % (len(names), cost, rem), flush=True)
        return {n: data.get('r%d' % i) for i, n in enumerate(names)}

    def fetch_heavy(self, name):
        """Single repo that exceeds GraphQL resource limits at 15 releases x 100 assets: retry with fewer releases (recorded in cache)."""
        if self.rest: return False                  # REST mode has no GraphQL release size limits
        for rel_n in (8, 4, 2, 1):
            try:
                res = self.query_batch([name], rel_n)
            except Exception as e:
                print('  heavy %s with %d releases failed (%s)' % (name, rel_n, str(e)[:60]), flush=True); continue
            atomic_write(cache_path(name), jdump({'requested': name, 'fetched_at': time.time(), 'node': res[name], 'reduced_releases': rel_n}))
            print('  heavy repo fetched with %d releases: %s' % (rel_n, name), flush=True)
            return True
        return False

    def fetch(self, names, batch):
        """Fetch with retry and batch halving; writes each repo to cache as soon as the batch returns."""
        queue = list(names)
        failed = []
        size = batch
        ok_streak = 0
        while queue:
            self.wait_if_low()
            chunk = queue[:size]
            try:
                res = self.query_batch(chunk, 0 if self.rest else 15)
            except urllib.error.HTTPError as e:
                code = e.code
                if code in (401, 403) and e.headers.get('x-ratelimit-remaining') == '0':
                    wait = max(5, int(e.headers.get('x-ratelimit-reset', time.time() + 60)) - time.time() + 5)
                    print('HTTP %s rate limited, sleeping %ds' % (code, wait), flush=True); time.sleep(min(wait, 3700)); continue
                if code == 401:
                    raise SystemExit('token rejected (HTTP 401)')
                res = self._retry_or_halve(chunk, size, 'HTTP %s' % code)
                if res is None:
                    size = max(1, len(chunk) // 2); ok_streak = 0
                    if len(chunk) == 1: failed.append(queue.pop(0))
                    continue
            except SystemExit:
                raise
            except Exception as e:
                res = self._retry_or_halve(chunk, size, type(e).__name__ + ' ' + str(e)[:120])
                if res is None:
                    size = max(1, len(chunk) // 2); ok_streak = 0
                    if len(chunk) == 1: failed.append(queue.pop(0))
                    continue
            if self.rest:
                items = []
                for n, node in res.items():
                    if not node: continue
                    if self.rest_skip and self.rest_skip(n, node):       # dropped by metadata curation anyway: no release request, no rate-limit spend
                        node['releases'] = {'nodes': []}; node['latestRelease'] = None; node['releases_skipped'] = True; self.rest_skipped += 1
                        continue
                    items.append((n, node['nameWithOwner'], (node.get('latestRelease') or {}).get('tagName')))
                got = self.rest.fetch_many([(full, tag) for n, full, tag in items])
                for n, full, tag in items:
                    r = got[full]
                    # a REST failure (even when an old release list is cached) must NOT refresh the repo cache: the repo keeps its old
                    # fetched_at, ages honestly, expires after --max-stale-days and counts toward the guard
                    if not r['ok'] or r['state'] == 'stale':
                        res.pop(n); self.rest_failed.append(n); continue
                    node = res[n]
                    node['releases'] = {'nodes': r['nodes']}
                    node['latestRelease'] = r['latest']
            now = time.time()
            for n, node in res.items():
                atomic_write(cache_path(n), jdump({'requested': n, 'fetched_at': now, 'node': node}))
            del queue[:len(chunk)]
            del res
            ok_streak += 1
            if ok_streak >= 8 and size < batch: size = min(batch, size * 2); ok_streak = 0
        return [n for n in failed if not self.fetch_heavy(n)] + list(self.rest_failed)

    def _retry_or_halve(self, chunk, size, why):
        print('  batch of %d failed (%s)' % (len(chunk), why), flush=True)
        time.sleep(3)
        return None


# ---------------------------------------------------------------- release logic
def asset_info(a):
    name = a['name']
    ek = P.ext_kind(name)
    is_apk = name.lower().endswith('.apk')
    o, ar, typ = CL.classify(name)
    if ek:
        os_, kind = EXT_OS[ek], ek
    elif is_apk:
        os_, kind = 'android', 'apk'
    else:
        os_ = o if o in ('windows', 'macos', 'linux', 'android', 'ios') else 'unknown'
        low = name.lower()
        if SIDECAR.search(low): kind = 'checksum'
        elif low.endswith(('.deb', '.rpm', '.snap', '.flatpak')): kind = low.rsplit('.', 1)[1]
        elif typ == 'portable': kind = 'portable'
        else: kind = 'other'
    return {'name': name, 'size': a.get('size'), 'downloads': a.get('downloadCount') or 0, 'url': a.get('downloadUrl'),
            'os': os_, 'arch': ar, 'kind': kind}


def pick_android(names):
    c = [n for n in names if n.lower().endswith('.apk') and not APK_HELPER.search(n.lower().replace('_', '-'))]
    if len(c) == 1: return c[0]
    if len(c) > 1:
        univ = [n for n in c if CL.classify(n)[1] == 'universal']
        if len(univ) == 1: return univ[0]
        noarch = [n for n in c if CL.classify(n)[1] == 'unknown']
        if len(noarch) == 1: return noarch[0]
    return None


def release_info(rel):
    assets = [asset_info(a) for a in ((rel.get('releaseAssets') or {}).get('nodes') or []) if a]
    names = [a['name'] for a in assets]
    picks = {'%s-%s' % c: P.pick(names, c[0], c[1]) for c in CELLS}
    picks['android'] = pick_android(names)
    return {'tag': rel.get('tagName'), 'name': rel.get('name'), 'prerelease': bool(rel.get('isPrerelease')),
            'published_at': rel.get('publishedAt'), 'notes_md': (rel.get('description') or '')[:NOTES_MAX],
            'assets': assets, 'picks': picks}


def release_platforms(r):
    return {EXT_OS[a['kind']] for a in r['assets'] if a['kind'] in EXT_OS}


def gather_releases(node):
    rels, seen = [], set()
    cand = [node.get('latestRelease')] + list((node.get('releases') or {}).get('nodes') or [])
    for r in cand:
        if not r or r.get('isDraft'): continue
        key = r.get('url') or r.get('tagName')
        if key in seen: continue
        seen.add(key); rels.append(r)
    rels.sort(key=lambda r: r.get('publishedAt') or '', reverse=True)
    return rels[:MAX_RELEASES + 1]


def short_desc(d, n=160):
    d = re.sub(r'\s+', ' ', d or '').strip()
    return d if len(d) <= n else d[:n - 1].rstrip() + '…'


TRUST_PICKER = 'picked by name only (evaluated on 300+ repos, not a safety check)'


def build_app(node, now):
    """-> (app dict, default_release) or (None, reason)."""
    meta = CUR.meta_from_graphql(node)
    rels_raw = gather_releases(node)
    if not rels_raw: return None, 'no_release'
    rels = [release_info(r) for r in rels_raw]
    if not any(release_platforms(r) for r in rels): return None, 'no_installer'
    stable = [r for r in rels if not r['prerelease']]
    pre = [r for r in rels if r['prerelease']]
    latest_stable = None
    lr = node.get('latestRelease')
    if lr and not lr.get('isDraft'):
        latest_stable = next((r for r in rels if r['tag'] == lr.get('tagName') and r['published_at'] == lr.get('publishedAt')), None)
    if latest_stable is None and stable: latest_stable = stable[0]
    latest_pre = pre[0] if pre else None
    default = latest_stable or latest_pre
    platforms = set()
    for r in (latest_stable, latest_pre):
        if r: platforms |= release_platforms(r)
    platforms = [p for p in PLATFORM_ORDER if p in platforms]
    topics = meta['topics']
    cat, mapped = CAT.categorize(topics)
    nwo = node['nameWithOwner']
    slug = nwo.lower().replace('/', '--')
    # "waktu rilis terakhir" = newest non-draft, non-prerelease release (rels excludes drafts); the download button and
    # `version` keep following GitHub's "Latest" flag (the maintainer's signal).
    stable_dates = [r['published_at'] for r in stable if r['published_at']]
    pub = max(stable_dates) if stable_dates else default['published_at']
    is_new = False
    if pub:
        try: is_new = (now - datetime.datetime.fromisoformat(pub.replace('Z', '+00:00'))).days < 14
        except Exception: pass
    owner = node.get('owner') or {}
    trust = {'curated_rules': True, 'rules': 'C1-C4b',
             'has_checksum_asset': any(a['kind'] == 'checksum' for a in default['assets']),
             'source': 'GitHub release, direct link', 'picker': TRUST_PICKER}
    if 'android' in platforms:
        trust['android_rule'] = 'apk picked by a separate name-only rule, not evaluated'
    dl = sum(a['downloads'] for r in rels for a in r['assets'])
    card = {'slug': slug, 'repo': nwo, 'name': nwo.split('/', 1)[1], 'owner': owner.get('login'), 'avatar': owner.get('avatarUrl'),
            'desc': short_desc(node.get('description')), 'stars': node.get('stargazerCount') or 0, 'platforms': platforms,
            'category': cat, 'dev': cat == 'developer', 'latest_release_at': pub, 'is_new': is_new, 'version': default['tag'],
            'trust': trust, 'trending': {'d7': None, 'd30': None, 'rank': None}}
    app = dict(card)
    app.update({'homepage': node.get('homepageUrl') or None, 'license': (node.get('licenseInfo') or {}).get('spdxId'),
                'topics': topics, 'forks': node.get('forkCount') or 0, 'downloads_total': dl, 'releases': rels})
    info = {'mapped': mapped, 'default': default, 'databaseId': node.get('databaseId')}
    return (card, app, info), None


# ---------------------------------------------------------------- candidate evaluation (shared by normal and github_trending candidates)
def evaluate_node(name, node, denied, now):
    """Curation + deny list + build for one fetched node. -> (res, reason, rules): res=(card, app, info) or None;
    reason is the key in `dropped`; rules is the list of failing C-codes (only for failed_curation)."""
    why = CUR.curate(CUR.meta_from_graphql(node))
    if why: return None, 'failed_curation', why
    if name.lower() in denied or node['nameWithOwner'].lower() in denied: return None, 'manual_deny', []
    res, reason = build_app(node, now)
    if res is None: return None, reason, []
    return res, None, []


def trend_reason_key(reason, rules):
    """Reason label used in stats.trending_candidates.rejected: the first failing C-code (C4a:x -> C4a) or the drop key."""
    return rules[0].split(':')[0] if rules else reason


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int)
    ap.add_argument('--only')
    ap.add_argument('--max-age-hours', type=float, default=20)
    ap.add_argument('--batch', type=int, default=25)
    ap.add_argument('--fetch-only', action='store_true')
    ap.add_argument('--history-dir', help='directory with snapshot-YYYY-MM-DD.json (default data/history)')
    ap.add_argument('--with-github-trending', action='store_true',
                    help='OPT-IN (default off): read github.com/trending (2 requests max) and curate its repos as extra candidates')
    ap.add_argument('--releases', choices=['rest', 'graphql'], default='rest',
                    help='rest (default): light GraphQL + REST releases with ETag; graphql: the old heavy query')
    ap.add_argument('--max-stale-days', type=float, default=PL.MAX_STALE_DAYS, help='a repo that cannot be fetched keeps its previous data this long')
    ap.add_argument('--max-not-fresh', type=float, default=PL.MAX_NOT_FRESH_FRACTION, help='fail (exit 4, nothing written) above this share of not-fresh repos')
    ap.add_argument('--strict', action='store_true', help='exit 3 when a fetch failed (old behaviour)')
    ap.add_argument('--no-changelog', action='store_true')
    args = ap.parse_args()
    partial = bool(args.limit or args.only)
    hist = pathlib.Path(args.history_dir) if args.history_dir else HIST

    cands = [args.only] if args.only else candidates()
    if args.limit: cands = cands[:args.limit]
    # github_trending candidates (names only, curated like every other candidate; never touch round3 / seen_repos.txt)
    github = TR.disabled_github()
    tfile = DATA / 'trending_candidates.txt'
    trend_only, trend_known = {}, 0
    if not partial:
        if args.with_github_trending:
            github = TR.get_github_trending(CACHE / 'github_trending.json')
            print('github trending: enabled, ok=%s' % github['ok'], flush=True)
            if github['ok']: TR.write_candidates(tfile, TR.read_candidates(tfile), github)
        have = {n.lower() for n in cands}
        tc = TR.read_candidates(tfile)
        for n in tc:
            if n.lower() in have: trend_known += 1; continue
            have.add(n.lower()); trend_only[n.lower()] = n; cands.append(n)
    tstats = {'seen': len(trend_only) + trend_known, 'added': 0, 'already_known': trend_known, 'rejected': {}}
    print('candidates:', len(cands), '(github_trending extra: %d)' % len(trend_only), flush=True)

    REPOS_CACHE.mkdir(parents=True, exist_ok=True)
    pending = [n for n in cands if not cache_fresh(n, args.max_age_hours)]
    print('to fetch:', len(pending), 'cached fresh:', len(cands) - len(pending), flush=True)
    failed, fx, rest_report = [], None, None
    if pending:
        tok = load_token()
        if not tok:
            print('no token (env GH_TOKEN or ~/.gh_token)', file=sys.stderr); return 2
        fx = Fetcher(tok)
        if args.releases == 'rest':
            fx.rest = RR.RestReleases(tok, CACHE / 'rest_releases')
            _denied = CUR.load_denied(DATA)
            fx.rest_skip = lambda n, node: bool(CUR.curate(CUR.meta_from_graphql(node))) or n.lower() in _denied or (node.get('nameWithOwner') or '').lower() in _denied
        failed = fx.fetch(pending, args.batch)
        if fx.rest:
            rest_report = fx.rest.report(); rest_report['skipped_rejected_by_metadata_or_denylist'] = fx.rest_skipped
        print('fetched; queries=%d points spent this run=%d remaining=%s' % (fx.queries, fx.session_cost, fx.remaining), flush=True)
        if rest_report: print('releases (REST): ' + json.dumps(rest_report), flush=True)

    def _fetched_at(n):
        q = cache_path(n)
        if not q.exists(): return None
        try: return json.loads(q.read_text(encoding='utf-8')).get('fetched_at')
        except Exception: return None
    fr = PL.classify_freshness(cands, _fetched_at, time.time(), args.max_age_hours, args.max_stale_days)
    guard_ok, n_bad, frac = PL.guard(len(cands), fr, args.max_not_fresh)
    fstats = PL.freshness_stats(fr, args.max_stale_days)
    print('freshness: fresh=%d stale_reused=%d stale_expired=%d missing=%d (not fresh %.1f%%)' % (
        fstats['fresh'], fstats['stale_reused'], fstats['stale_expired'], fstats['missing'], 100 * frac), flush=True)
    if args.strict and failed:
        print('remaining %d unfetched (--strict)' % len(failed)); return 3
    if args.fetch_only: return 0
    if not partial and not guard_ok:
        print('GUARD: %d of %d repos are not fresh (limit %.0f%%). Nothing was written; the previous site data stays.' % (n_bad, len(cands), 100 * args.max_not_fresh), file=sys.stderr)
        return 4
    unusable = {n.lower(): 'stale_expired' for n, _ in fr['expired']}
    unusable.update({n.lower(): 'not_fetched' for n in fr['missing']})
    reasons = {}

    # ---- build phase
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    denied = CUR.load_denied(DATA)
    snaps = TR.load_snapshots(hist)
    outdir = (ROOT / 'data' / 'catalog_test_out') if partial else OUT   # test runs never touch site/public/data
    out_apps = outdir / 'apps'
    out_apps.mkdir(parents=True, exist_ok=True)
    dropped = {'failed_curation': 0, 'manual_deny': 0, 'not_found': 0, 'duplicate_id': 0, 'no_release': 0, 'no_installer': 0, 'stale_expired': 0, 'not_fetched': 0}
    by_rule = {}
    cards, ids, written = [], set(), set()
    snapshot, uncategorized, platforms_empty = {}, 0, 0
    sil = {'%s-%s' % c: {'n': 0, 'silent': 0} for c in CELLS}
    sil_android = {'n': 0, 'silent': 0}
    for name in cands:
        if name.lower() in unusable:
            k = unusable[name.lower()]; dropped[k] += 1; reasons[name.lower()] = k
            continue
        j = json.loads(cache_path(name).read_text(encoding='utf-8'))
        node = j.get('node')
        is_trend = name.lower() in trend_only
        if not node or node['databaseId'] in ids:
            k = 'not_found' if not node else 'duplicate_id'
            dropped[k] += 1; reasons[name.lower()] = k
            if is_trend: tstats['rejected'][k] = tstats['rejected'].get(k, 0) + 1
            continue
        ids.add(node['databaseId'])
        res, reason, why = evaluate_node(name, node, denied, now)
        if res is None:
            dropped[reason] += 1; reasons[name.lower()] = (why[0].split(':')[0] if why else reason)
            for w in why: by_rule[w.split(':')[0]] = by_rule.get(w.split(':')[0], 0) + 1
            if is_trend:
                k = trend_reason_key(reason, why); tstats['rejected'][k] = tstats['rejected'].get(k, 0) + 1
            continue
        card, app, info = res
        if is_trend:
            tstats['added'] += 1
            card['sources'] = app['sources'] = ['github_trending']
        d = info['default']
        for os_ in ('windows', 'macos', 'linux'):
            for arch in ('x64', 'arm64'):
                if (os_, arch) not in CELLS: continue
                if any(a['kind'] in EXT_OS and EXT_OS[a['kind']] == os_ for a in d['assets']):
                    k = sil['%s-%s' % (os_, arch)]; k['n'] += 1
                    if d['picks']['%s-%s' % (os_, arch)] is None: k['silent'] += 1
        if any(a['kind'] == 'apk' for a in d['assets']):
            sil_android['n'] += 1
            if d['picks']['android'] is None: sil_android['silent'] += 1
        if not info['mapped']: uncategorized += 1
        if not card['platforms']: platforms_empty += 1
        dl = app['downloads_total']
        snapshot[card['repo']] = {'stars': card['stars'], 'downloads': dl}
        atomic_write(out_apps / (card['slug'] + '.json'), jdump(app))
        written.add(card['slug'] + '.json')
        cards.append(card)
        del j, node, app

    # ---- trending: star growth from our own snapshots (trending.py); rewrite only the app files that carry a value
    ready, rows, base = TR.compute([{'repo': c['repo'], 'slug': c['slug'], 'stars': c['stars']} for c in cards], snaps, today)
    ranked = TR.rank_rows(rows)
    for c, r in zip(cards, rows):
        c['trending'] = {'d7': r['d7'], 'd30': r['d30'], 'rank': r['rank']}
        if r['d7'] is not None or r['d30'] is not None:
            p = out_apps / (c['slug'] + '.json')
            a = json.loads(p.read_text(encoding='utf-8')); a['trending'] = c['trending']
            atomic_write(p, jdump(a))

    cards.sort(key=lambda c: -c['stars'])
    gen = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    cost = {'points_spent_total': 0, 'queries': 0}
    if COST_LOG.exists():
        for l in COST_LOG.read_text(encoding='utf-8').splitlines():
            try: r = json.loads(l); cost['points_spent_total'] += r.get('cost') or 0; cost['queries'] += 1
            except Exception: pass
    cat_counts = {c: 0 for c in CAT.CATEGORY_IDS}
    plat_counts = {p: 0 for p in PLATFORM_ORDER}
    for c in cards:
        cat_counts[c['category']] += 1
        for p in c['platforms']: plat_counts[p] += 1
    share = {}
    for k, v in list(sil.items()) + [('android', sil_android)]:
        share[k] = {'n': v['n'], 'silent': v['silent'], 'share': round(v['silent'] / v['n'], 4) if v['n'] else None}
    # ---- changelog: who entered / left the catalog (and why), plus new candidates of the day
    cur = {c['repo'].lower(): {'repo': c['repo'], 'stars': c['stars']} for c in cards}
    dmap = discovered_map()
    sources = {}
    for k in cur:
        sources[k] = dmap[k][1] if k in dmap else 'candidate_pool'
    prev_c = None
    try: prev_c = json.loads((CHANGELOG / 'desktop-candidates.json').read_text(encoding='utf-8')).get('names')
    except Exception: pass
    new_names = [] if prev_c is None else [n for n in cands if n.lower() not in {x.lower() for x in prev_c}]
    new_rej = {}
    for n in new_names:
        if n.lower() in reasons: new_rej[reasons[n.lower()]] = new_rej.get(reasons[n.lower()], 0) + 1
    new_added = sum(1 for n in new_names if n.lower() in cur)
    changelog_entry = None
    if not partial and not args.no_changelog:
        changelog_entry = PL.record_changelog(CHANGELOG, 'desktop', today.isoformat(), cur, reasons, sources,
                                              extra={'new_candidates': {'seen': len(new_names), 'added': new_added, 'rejected': new_rej},
                                                     'stale_reused': fstats['stale_reused']})
        atomic_write(CHANGELOG / 'desktop-candidates.json', jdump({'date': today.isoformat(), 'names': list(cands)}))
    stats = {'generated_at': gen, 'partial_run': partial, 'freshness': fstats, 'releases_rest': rest_report, 'candidates': len(cands), 'count': len(cards), 'platforms': plat_counts,
             'categories': cat_counts, 'dropped': dropped, 'failed_curation_by_rule': by_rule, 'uncategorized': uncategorized,
             'dev_category': cat_counts['developer'], 'apps_without_platform_badge': platforms_empty,
             'picker_silent_share': share, 'trending_candidates': tstats,
             'trending': {'ready': ready, 'ranked': len(ranked), 'badges': sum(1 for r in ranked if TR.has_badge(r['d7'], r['rank'], r['stars']))},
             'picker_silent_share_note': 'denominator = apps whose default release (latest stable, else latest pre-release) has >=1 strict-extension asset for that OS',
             'graphql': cost}
    trend = TR.trending_doc(ranked, ready, gen, snaps, base, github, today, daily=TR.daily_top(rows, snaps, today))
    atomic_write(outdir / 'catalog.json', jdump({'generated_at': gen, 'picker_sha256': PICKER_SHA, 'count': len(cards), 'apps': cards}))
    atomic_write(outdir / 'stats.json', jdump(stats, 2))
    atomic_write(outdir / 'trending.json', jdump(trend))
    if not partial:
        PL.update_meta(outdir, 'desktop', gen)
        atomic_write(outdir / 'changelog.json', jdump({'generated_at': gen, 'section': 'desktop', 'entries': PL.published_changelog(CHANGELOG, 'desktop')}))
    if not partial:
        for f in out_apps.glob('*.json'):
            if f.name not in written: f.unlink()
        atomic_write(hist / ('snapshot-%s.json' % today.isoformat()), jdump(snapshot))
    else:
        print('partial run: outputs in', outdir)
    print(json.dumps({k: stats[k] for k in ('count', 'dropped', 'uncategorized', 'dev_category')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
