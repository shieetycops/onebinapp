"""AI-tools catalog builder (SPEC_AI.md sections 1-3).  Run:  python -I scripts/catalog/build_ai.py
Options: --target N (200)  --cap N (1500)  --batch N (10)  --max-age-hours H (20)  --registry-max-age-hours H (1)  --offline
         --history-dir DIR (ai-snapshot-*.json; default data/history)  --with-github-trending (OPT-IN, default off; see trending.py)
Phases: (1) registry crawl (one full crawl, resumable, cached) (2) GitHub topic searches (cached) (3) star lookup for registry-only
repos (GraphQL, tiny) (4) rank by stars, fetch heavy GraphQL batches in star order, curate sequentially until --target entries pass or
--cap repos are examined (5) write site/public/data/{catalog-ai.json,stats-ai.json,ai/<slug>.json} + data/history/ai-snapshot-DATE.json.
Cache: data/catalog_cache_ai/ (never published). Token: env GH_TOKEN / ~/.gh_token via build_catalog.load_token; never printed or stored.
Reuses atomic_write/jdump/load_token/Fetcher._post/wait_if_low from build_catalog (imported; that file is not modified).
Decisions are listed in DECISIONS (printed in stats-ai.json)."""
import sys, os, re, json, time, glob, pathlib, argparse, datetime, http.client, urllib.request, urllib.error, urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import build_catalog as B                         # noqa: E402  (hash-verifies picker/classifier at import)
import curation_ai as CU                          # noqa: E402
import install_ai as IA                           # noqa: E402
import categories_ai as CA                        # noqa: E402
import trending as TR                             # noqa: E402
import usage_ai as USG                            # noqa: E402
import pipeline as PL                             # noqa: E402

ROOT, DATA, OUT, HIST = B.ROOT, B.DATA, B.OUT, B.HIST
CHANGELOG = DATA / 'changelog'
CACHE = DATA / 'catalog_cache_ai'
COST_LOG = CACHE / 'cost_log_ai.jsonl'
UA = 'catalog-builder-ai'
TOPICS = ['mcp-server', 'mcp', 'claude-skills', 'agent-skills', 'claude-code-plugin', 'claude-code-plugins', 'claude-code-skills']
REGISTRY_URL = 'https://registry.modelcontextprotocol.io/v0.1/servers'
SKILL_PROBE_PER_DIR = 10
SKILL_PROBE_ROOT = 8
IGNORE_ROOT = {'node_modules', 'src', 'docs', 'doc', 'test', 'tests', 'dist', 'build', 'examples', 'example', 'assets', 'images',
               'scripts', 'packages', 'lib', 'vendor', 'public', 'static', 'skills'}
FORBIDDEN = re.compile(r'\b(' + 'am' + 'an' + r'|safe)\b', re.I)

DECISIONS = [
    'Each rejected repo gets only its FIRST failing code, in order R1..R8.',
    'R2: missing release or pushedAt counts as old. R4: registry server.json counts as a parsed manifest.',
    'R6 applied exactly as written (README code blocks + inline code, package.json scripts, plugin/marketplace/server.json strings).',
    'R7 manifest-vs-manifest only (server.json identifier vs package.json/pyproject name; README JSON config args vs package.json name); skipped with repository.subfolder or private/workspace root package.json.',
    'README is read only from HEAD:README.md (case-sensitive).',
    'Added .agents/plugins/marketplace.json to fetched manifests (needed for the Codex plugin cell; it is a plugin manifest for type detection too).',
    'Install launch spec only from server.json (registry or repo) packages npm/pypi (stdio) or streamable-http remotes; package.json/pyproject names are never turned into npx/uvx commands. oci/nuget/mcpb/sse -> none.',
    'Preference when several launch options exist: npm, then pypi, then remote.',
    'tools[] = tools with at least one non-none install method (matrix of install_methods.md); .cursor-plugin/.codex-plugin alone do not add a tool because those matrix cells are "no button".',
    'VS Code plugin deeplink only when the repo has a .claude-plugin/{plugin,marketplace}.json or root plugin.json (the research file names no other manifest).',
    'Cursor deeplink: config = bare server object (verified against the official example), compact JSON, base64, then percent-encoding of +,/ (= kept).',
    'Registry monorepos: one entry per GitHub repo (deduped by databaseId); primary server = first without repository.subfolder, else first by name; all server names kept in sources.',
    'access.api_keys / files / terminal / network are plain strings (or exactly "tidak diketahui"); api_keys_list holds the structured env var list; disclaimer is the fixed sentence.',
    'Entries whose generated install text/identifiers contain either of the two banned words (whole-word match) are skipped (counted as forbidden_word_identifier); descriptions/names/topics containing them are masked with ***.',
    'ai-snapshot file holds stars for every repo that was fetched (examined), key = nameWithOwner.',
]


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ http (token never logged)
def http_json(url, headers=None, retries=5, timeout=90):
    h = {'User-Agent': UA, 'Accept': 'application/json'}
    h.update(headers or {})
    wait = 2
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return json.loads(f.read().decode('utf-8')), dict(f.headers)
        except urllib.error.HTTPError as e:
            code = e.code
            if code in (403, 429):
                rem = e.headers.get('x-ratelimit-remaining')
                reset = e.headers.get('x-ratelimit-reset') or e.headers.get('retry-after')
                w = wait * 5
                try:
                    r = float(reset)
                    w = max(5, (r - time.time() if r > 1e9 else r) + 3)
                except Exception:
                    pass
                log('  HTTP %s (remaining=%s), waiting %ds' % (code, rem, min(w, 120)))
                time.sleep(min(w, 120))
            elif code in (500, 502, 503, 504):
                log('  HTTP %s, retry in %ds' % (code, wait)); time.sleep(wait)
            else:
                raise RuntimeError('HTTP %s for %s' % (code, url.split('?')[0]))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, http.client.HTTPException) as e:      # IncompleteRead etc.
            log('  network error %s, retry in %ds' % (type(e).__name__, wait)); time.sleep(wait)
        wait = min(wait * 2, 60)
    raise RuntimeError('giving up on ' + url.split('?')[0])


def read_json(p):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
    except Exception:
        return None


def fresh(j, hours):
    return bool(j) and (time.time() - j.get('fetched_at', 0)) < hours * 3600


# ------------------------------------------------------------------ 1. registry
def github_repo_from_url(u):
    if not isinstance(u, str): return None
    m = re.match(r'^(?:https?://|git\+https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)', u.strip())
    if not m: return None
    o, r = m.group(1), m.group(2)
    if r.lower().endswith('.git'): r = r[:-4]
    if not r or o in ('.', '..'): return None
    return '%s/%s' % (o, r)


FULL_CRAWL_EVERY_DAYS = 7      # in between, only records changed since the last crawl are read (registry docs: aggregators should use updated_since)
REGISTRY_RETRIES = 8           # exponential backoff up to 60 s: rides out a few minutes of registry trouble


def _is_latest_active(rec):
    meta = (rec.get('_meta') or {}).get('io.modelcontextprotocol.registry/official') or {}
    return bool(meta.get('isLatest')), meta.get('status', 'active')


def merge_incremental(servers, records, skipped):
    """servers: stored list of latest+active server dicts.  records: raw registry records changed since the last crawl.
    A latest+active record replaces/inserts its server (by name); a latest record that is no longer active removes it;
    records of older versions are ignored.  -> (new list, counts)"""
    idx = {s.get('name'): i for i, s in enumerate(servers)}
    out = list(servers)
    gone = set()
    cnt = {'updated': 0, 'added': 0, 'removed': 0}
    for rec in records:
        latest, st = _is_latest_active(rec)
        if not latest:
            skipped['not_latest'] = skipped.get('not_latest', 0) + 1
            continue
        srv = rec.get('server') or {}
        nm = srv.get('name')
        if st != 'active':
            skipped[st] = skipped.get(st, 0) + 1
            if nm in idx and nm not in gone: gone.add(nm); cnt['removed'] += 1
            continue
        if nm in idx:
            out[idx[nm]] = srv; cnt['updated'] += 1; gone.discard(nm)
        else:
            idx[nm] = len(out); out.append(srv); cnt['added'] += 1
    if gone: out = [x for x in out if x.get('name') not in gone]
    return out, cnt


def _iso_utc(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def registry_crawl(max_age_h, offline=False):
    """Full crawl when there is no complete copy or it is older than FULL_CRAWL_EVERY_DAYS; otherwise an incremental crawl with
    updated_since.  Progress of a full crawl goes to registry.partial.json (resumable); registry.json is replaced ONLY by a finished
    crawl, so a crawl that dies half-way never destroys the previous complete copy (registry_or_previous falls back to it)."""
    p = CACHE / 'registry.json'
    pp = CACHE / 'registry.partial.json'
    j = read_json(p) or {}
    if j.get('complete') and (fresh(j, max_age_h) or offline):
        log('registry: using cache (%d latest-active servers)' % len(j['servers'])); return j
    if offline and j: return j
    t0 = time.time()
    full_age_days = (t0 - (j.get('full_at') or 0)) / 86400.0 if j.get('complete') else None
    if j.get('complete') and j.get('servers') and full_age_days is not None and full_age_days < FULL_CRAWL_EVERY_DAYS and j.get('started_at'):
        since = _iso_utc(j['started_at'] - 86400)           # one day of overlap: nothing can slip through a slow previous crawl
        log('registry: incremental crawl updated_since=%s (full crawl was %.1f days ago)' % (since, full_age_days))
        recs, cursor, pages = [], None, 0
        while True:
            q = {'limit': '100', 'updated_since': since}
            if cursor: q['cursor'] = cursor
            d, _ = http_json(REGISTRY_URL + '?' + urllib.parse.urlencode(q), retries=REGISTRY_RETRIES)
            recs += d.get('servers') or []
            pages += 1
            cursor = (d.get('metadata') or {}).get('nextCursor')
            if not cursor: break
            time.sleep(0.3)
        skipped = dict(j.get('skipped_status') or {})
        servers, cnt = merge_incremental(j['servers'], recs, skipped)
        state = dict(j, servers=servers, skipped_status=skipped, started_at=t0, fetched_at=time.time(), complete=True, mode='incremental',
                     incremental={'since': since, 'pages': pages, 'records': len(recs), **cnt})
        B.atomic_write(p, B.jdump(state))
        log('registry: incremental done pages=%d records=%d %s -> %d latest-active servers' % (pages, len(recs), cnt, len(servers)))
        return state
    part = read_json(pp)
    state = part if (part and not part.get('complete')) else {'servers': [], 'cursor': None, 'pages': 0, 'records_seen': 0, 'skipped_status': {}, 'started_at': t0}
    log('registry: FULL crawl start (resume cursor=%s)' % bool(state.get('cursor')))
    while True:
        q = {'limit': '100'}
        if state['cursor']: q['cursor'] = state['cursor']
        try:
            d, _ = http_json(REGISTRY_URL + '?' + urllib.parse.urlencode(q), retries=REGISTRY_RETRIES)
        except Exception:
            B.atomic_write(pp, B.jdump(state))            # keep the progress so the next run resumes
            raise
        for rec in d.get('servers') or []:
            state['records_seen'] += 1
            latest, st = _is_latest_active(rec)
            if not latest or st != 'active':
                k = 'not_latest' if not latest else st
                state['skipped_status'][k] = state['skipped_status'].get(k, 0) + 1
                continue
            state['servers'].append(rec.get('server') or {})
        state['pages'] += 1
        state['cursor'] = (d.get('metadata') or {}).get('nextCursor')
        state['fetched_at'] = time.time()
        state['complete'] = not state['cursor']
        if state['complete']:
            state['full_at'] = time.time(); state['mode'] = 'full'
            B.atomic_write(p, B.jdump(state))
            try: pp.unlink()
            except OSError: pass
        elif state['pages'] % 5 == 0:
            B.atomic_write(pp, B.jdump(state))
        if state['pages'] % 20 == 0: log('  registry pages=%d records=%d latest_active=%d' % (state['pages'], state['records_seen'], len(state['servers'])))
        if state['complete']: break
        time.sleep(0.3)
    log('registry: done pages=%d records=%d latest_active=%d' % (state['pages'], state['records_seen'], len(state['servers'])))
    return state


def registry_or_previous(max_age_h, offline=False):
    """Registry crawl; if it fails, the previous COMPLETE copy is used (logged and counted), otherwise the error propagates."""
    try:
        return registry_crawl(max_age_h, offline), None
    except Exception as e:
        prev = read_json(CACHE / 'registry.json')
        if prev and prev.get('complete') and prev.get('servers'):
            age = round((time.time() - (prev.get('fetched_at') or 0)) / 86400.0, 2)
            log('registry crawl FAILED (%s); using the previous complete copy (%s days old)' % (type(e).__name__, age))
            return prev, {'failed': type(e).__name__, 'previous_copy_age_days': age}
        raise


# ------------------------------------------------------------------ 2. topic search
def topic_search(token, max_age_h, offline=False):
    out = {}
    d = CACHE / 'search'
    d.mkdir(parents=True, exist_ok=True)
    for t in TOPICS:
        items = []
        for pg in range(1, 6):
            p = d / ('%s-p%d.json' % (t, pg))
            j = read_json(p)
            if not (j and (fresh(j, max_age_h) or offline)):
                if offline: break
                q = urllib.parse.urlencode({'q': 'topic:%s stars:>=20' % t, 'sort': 'stars', 'order': 'desc', 'per_page': '100', 'page': str(pg)})
                time.sleep(2.5)                     # search API: own per-minute limit
                try:
                    r, _ = http_json('https://api.github.com/search/repositories?' + q,
                                     {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'})
                except RuntimeError as e:
                    log('  search %s p%d failed: %s' % (t, pg, str(e)[:80])); break
                j = {'fetched_at': time.time(), 'total_count': r.get('total_count'),
                     'items': [{'full_name': i['full_name'], 'id': i['id'], 'stars': i['stargazers_count']} for i in r.get('items') or []]}
                B.atomic_write(p, B.jdump(j))
                log('  search topic=%s page=%d items=%d total=%s' % (t, pg, len(j['items']), j['total_count']))
            items += j['items']
            if len(j['items']) < 100: break
        out[t] = items
    return out


# ------------------------------------------------------------------ GraphQL (own queries, own cost log)
class AIFetcher(B.Fetcher):
    def gql(self, query):
        self.wait_if_low()
        resp = self._post(query)
        data = resp.get('data')
        if not data:
            raise RuntimeError('graphql no data: ' + json.dumps(resp.get('errors'))[:200])
        for e in resp.get('errors') or []:
            if e.get('type') != 'NOT_FOUND' and ('limit' in json.dumps(e).lower() or 'timeout' in json.dumps(e).lower()):
                raise RuntimeError('graphql limit: ' + json.dumps(e)[:160])
        rl = data.get('rateLimit') or {}
        self.remaining = rl.get('remaining')
        try:
            self.reset_at = datetime.datetime.fromisoformat(rl['resetAt'].replace('Z', '+00:00')).timestamp()
        except Exception:
            self.reset_at = time.time() + 600
        self.session_cost += rl.get('cost') or 0
        self.queries += 1
        with open(COST_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': int(time.time()), 'cost': rl.get('cost'), 'remaining': rl.get('remaining')}) + '\n')
        return data, rl

    def with_retry(self, query, tries=3):
        last = None
        for i in range(tries):
            try:
                return self.gql(query)
            except urllib.error.HTTPError as e:
                if e.code == 401: raise SystemExit('token rejected (HTTP 401)')
                last = 'HTTP %s' % e.code
            except SystemExit:
                raise
            except Exception as e:
                last = type(e).__name__ + ' ' + str(e)[:100]
            time.sleep(3 * (i + 1))
        raise RuntimeError(last)


def star_lookup(fetcher, names, max_age_h, offline=False):
    """names: list -> dict lower-name -> {id, stars, name}|None. Cached in stars.json."""
    p = CACHE / 'stars.json'
    c = read_json(p) or {'fetched_at': 0, 'repos': {}}
    repos = c['repos']
    todo = [n for n in names if n.lower() not in repos]
    if offline: todo = []
    for i in range(0, len(todo), 100):
        chunk = todo[i:i + 100]
        parts = ['r%d: repository(owner: %s, name: %s) { databaseId nameWithOwner stargazerCount }' % (k, json.dumps(n.split('/')[0]), json.dumps(n.split('/', 1)[1])) for k, n in enumerate(chunk)]
        data, rl = fetcher.with_retry('query { rateLimit { cost remaining resetAt } ' + ' '.join(parts) + ' }')
        for k, n in enumerate(chunk):
            r = data.get('r%d' % k)
            repos[n.lower()] = {'id': r['databaseId'], 'stars': r['stargazerCount'], 'name': r['nameWithOwner']} if r else None
        c['fetched_at'] = time.time()
        B.atomic_write(p, B.jdump(c))
        log('  stars lookup %d/%d cost=%s remaining=%s' % (min(i + 100, len(todo)), len(todo), rl.get('cost'), rl.get('remaining')))
    return {n.lower(): repos.get(n.lower()) for n in names}


BLOBS = CU.MANIFEST_PATHS + ['README.md']
TREES = ['', 'skills', '.claude/skills', '.agents/skills']
FRAG = '''
fragment F on Repository {
  databaseId nameWithOwner description stargazerCount forkCount isFork isArchived isDisabled
  owner { login __typename avatarUrl ... on User { createdAt } ... on Organization { createdAt } }
  repositoryTopics(first: 20) { nodes { topic { name } } }
  licenseInfo { spdxId }
  homepageUrl pushedAt
  latestRelease { publishedAt }
%s
}
''' % '\n'.join(
    ['  m%d: object(expression: %s) { ... on Blob { text isTruncated } }' % (i, json.dumps('HEAD:' + p)) for i, p in enumerate(BLOBS)] +
    ['  t%d: object(expression: %s) { ... on Tree { entries { name type } } }' % (i, json.dumps('HEAD:' + p)) for i, p in enumerate(TREES)])


def normalize(node):
    """GraphQL node -> compact cache record (texts trimmed)."""
    if not node: return None
    texts, truncated = {}, []
    readme = None
    for i, p in enumerate(BLOBS):
        b = node.get('m%d' % i)
        if not b or b.get('text') is None: continue
        if p == 'README.md': readme = b['text'][:CU.README_MAX]
        elif p == 'SKILL.md': texts[p] = b['text'][:8000]
        elif b.get('isTruncated'): truncated.append(p)
        else: texts[p] = b['text']
    trees = {}
    for i, p in enumerate(TREES):
        t = node.get('t%d' % i)
        if t and t.get('entries') is not None: trees[p] = [[e['name'], e['type']] for e in t['entries']]
    core = {k: node.get(k) for k in ('databaseId', 'nameWithOwner', 'description', 'stargazerCount', 'forkCount', 'isFork', 'isArchived',
                                     'isDisabled', 'owner', 'licenseInfo', 'homepageUrl', 'pushedAt', 'latestRelease')}
    core['topics'] = [n['topic']['name'] for n in (node.get('repositoryTopics') or {}).get('nodes') or []]
    return {'node': core, 'texts': texts, 'readme': readme, 'trees': trees, 'truncated_manifests': truncated}


def slug_of(name): return name.lower().replace('/', '--')


def repo_cache(name): return CACHE / 'repos' / (slug_of(name) + '.json')


def fetch_repos(fetcher, names, batch, max_age_h, offline):
    todo = [n for n in names if not fresh(read_json(repo_cache(n)), max_age_h) or (read_json(repo_cache(n)) or {}).get('error')]
    if offline: return []
    failed, size, queue = [], batch, list(todo)
    while queue:
        chunk = queue[:size]
        parts = ['r%d: repository(owner: %s, name: %s) { ...F }' % (i, json.dumps(n.split('/')[0]), json.dumps(n.split('/', 1)[1])) for i, n in enumerate(chunk)]
        try:
            data, rl = fetcher.with_retry('query { rateLimit { cost remaining resetAt } ' + ' '.join(parts) + ' }' + FRAG)
        except Exception as e:
            log('  batch of %d failed (%s)' % (len(chunk), str(e)[:80]))
            if len(chunk) == 1:
                prev = read_json(repo_cache(chunk[0]))
                if not (prev and prev.get('rec')):       # keep the previous good copy (reused as "stale"); record an error only when there is none
                    B.atomic_write(repo_cache(chunk[0]), B.jdump({'fetched_at': time.time(), 'error': str(e)[:100]}))
                failed.append(chunk[0]); queue.pop(0)
            size = max(1, len(chunk) // 2); continue
        now = time.time()
        for i, n in enumerate(chunk):
            B.atomic_write(repo_cache(n), B.jdump({'fetched_at': now, 'rec': normalize(data.get('r%d' % i))}))
        log('  heavy batch %d repos cost=%s remaining=%s' % (len(chunk), rl.get('cost'), rl.get('remaining')))
        del queue[:len(chunk)]
        del data
        if size < batch and len(queue) > 0: size = min(batch, size * 2)
    return failed


def skill_paths(rec):
    tr = rec.get('trees') or {}
    paths = []
    for d in ('skills', '.claude/skills', '.agents/skills'):
        dirs = [n for n, t in tr.get(d, []) if t == 'tree'][:SKILL_PROBE_PER_DIR]
        paths += ['%s/%s/SKILL.md' % (d, n) for n in dirs]
    root = [n for n, t in tr.get('', []) if t == 'tree' and not n.startswith('.') and n.lower() not in IGNORE_ROOT][:SKILL_PROBE_ROOT]
    paths += ['%s/SKILL.md' % n for n in root]
    return paths


def skills_cache(name): return CACHE / 'skills' / (slug_of(name) + '.json')


def fetch_skills(fetcher, jobs, batch):
    """jobs: {name: [paths]} -> writes skills cache per repo."""
    names = [n for n, ps in jobs.items() if ps and not skills_cache(n).exists()]
    for n, ps in jobs.items():
        if not ps and not skills_cache(n).exists(): B.atomic_write(skills_cache(n), B.jdump({'fetched_at': time.time(), 'files': {}}))
    for i in range(0, len(names), batch):
        chunk = names[i:i + batch]
        parts = []
        for k, n in enumerate(chunk):
            objs = ' '.join('s%d: object(expression: %s) { ... on Blob { text } }' % (j, json.dumps('HEAD:' + p)) for j, p in enumerate(jobs[n]))
            parts.append('r%d: repository(owner: %s, name: %s) { %s }' % (k, json.dumps(n.split('/')[0]), json.dumps(n.split('/', 1)[1]), objs))
        try:
            data, rl = fetcher.with_retry('query { rateLimit { cost remaining resetAt } ' + ' '.join(parts) + ' }')
        except Exception as e:
            log('  skill batch failed (%s); skipped (rerun resumes)' % str(e)[:80]); continue
        for k, n in enumerate(chunk):
            r = data.get('r%d' % k) or {}
            files = {}
            for j, p in enumerate(jobs[n]):
                b = r.get('s%d' % j)
                if b and b.get('text'): files[p] = b['text'][:8000]
            B.atomic_write(skills_cache(n), B.jdump({'fetched_at': time.time(), 'files': files}))
        log('  skill batch %d repos cost=%s remaining=%s' % (len(chunk), rl.get('cost'), rl.get('remaining')))


def skill_jobs(chunk, now):
    jobs = {}
    for c in chunk:
        j = read_json(repo_cache(c['name']))
        rec = (j or {}).get('rec')
        if rec and quick_r123(rec, now) and not (rec['texts'].get('SKILL.md') and CU.parse_skill('SKILL.md', rec['texts']['SKILL.md'])):
            jobs[c['name']] = skill_paths(rec)
    return jobs


# ------------------------------------------------------------------ candidates
def build_candidates(registry, topics_res, trend_cands=None):
    cands = {}      # lower name -> {name, id, stars, sources[], servers[]}
    reg_stats = {'latest_active': len(registry['servers']), 'with_github_repo': 0, 'no_github_repo': 0}
    reg_repos = {}
    for s in registry['servers']:
        repo = github_repo_from_url((s.get('repository') or {}).get('url'))
        if not repo:
            reg_stats['no_github_repo'] += 1; continue
        reg_stats['with_github_repo'] += 1
        reg_repos.setdefault(repo.lower(), {'name': repo, 'servers': []})['servers'].append(s)
    for k, v in reg_repos.items():
        cands[k] = {'name': v['name'], 'id': None, 'stars': None, 'sources': [], 'servers': v['servers']}
        for s in v['servers'][:5]:
            cands[k]['sources'].append({'kind': 'registry', 'ref': s.get('name')})
    reg_stats['unique_github_repos'] = len(reg_repos)
    topic_counts = {}
    for t, items in topics_res.items():
        topic_counts[t] = len(items)
        for it in items:
            k = it['full_name'].lower()
            c = cands.setdefault(k, {'name': it['full_name'], 'id': None, 'stars': None, 'sources': [], 'servers': []})
            c['id'], c['stars'] = it['id'], it['stars']
            c['sources'].append({'kind': 'gh_topic', 'ref': t})
    # github_trending candidates (names only): tag repos we already know; unknown ones are examined separately (trend_only)
    known = 0
    for name, tags in (trend_cands or {}).items():
        k = name.lower()
        if k in cands: known += 1
        else: cands[k] = {'name': name, 'id': None, 'stars': None, 'sources': [], 'servers': [], 'trend_only': True}
        for tg in tags:
            ref = tg.split(':', 1)[1] if ':' in tg else tg
            cands[k]['sources'].append({'kind': 'github_trending', 'ref': ref})
    reg_stats['github_trending_already_known'] = known
    return cands, reg_stats, topic_counts


def primary_server(servers):
    if not servers: return None
    ss = sorted(servers, key=lambda s: ((s.get('repository') or {}).get('subfolder') not in (None, ''), s.get('name', '')))
    return ss[0]


# ------------------------------------------------------------------ evaluation
def evaluate(name, cand, now):
    """-> dict(status, code, detail, rec, M, types, from_registry) from caches only."""
    j = read_json(repo_cache(name))
    if not j or j.get('error') or not j.get('rec'):
        return {'status': 'fetch_failed' if j and j.get('error') else 'missing', 'code': None}
    rec = j['rec']
    age_days = max(0.0, (time.time() - (j.get('fetched_at') or 0)) / 86400.0)
    node = dict(rec['node'])
    node['pushedAt'] = node.get('pushedAt')
    reg_srv = primary_server(cand.get('servers'))
    sk = (read_json(skills_cache(name)) or {}).get('files') or {}
    M = CU.parse_manifests(rec['texts'], reg_srv, sk)
    ok, code, detail, types = CU.curate(node, M, rec.get('readme'), now, bool(cand.get('servers')))
    return {'status': 'ok' if ok else 'rejected', 'code': code, 'detail': detail, 'rec': rec, 'M': M, 'types': types, 'node': node, 'age_days': age_days}


def quick_r123(rec, now):
    node = rec['node']
    owner = node.get('owner') or {}
    if not owner.get('login') or node.get('isFork'): return False
    c = CU.parse_ts(owner.get('createdAt'))
    if not c or (now - c).days < CU.OWNER_MIN_DAYS: return False
    d = [x for x in (CU.parse_ts(node.get('pushedAt')), CU.parse_ts((node.get('latestRelease') or {}).get('publishedAt'))) if x]
    if not d or (now - max(d)).days > CU.ACTIVE_DAYS: return False
    return not (node.get('isArchived') or node.get('isDisabled'))


# ------------------------------------------------------------------ output
def mask(s):
    return FORBIDDEN.sub('***', s) if isinstance(s, str) else s


def short(d, n=160):
    d = re.sub(r'\s+', ' ', d or '').strip()
    return d if len(d) <= n else d[:n - 1].rstrip() + '…'


def scan_forbidden(o, path=''):
    out = []
    if isinstance(o, str):
        if FORBIDDEN.search(o): out.append(path)
    elif isinstance(o, dict):
        for k, v in o.items(): out += scan_forbidden(v, path + '/' + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o): out += scan_forbidden(v, path + '/%d' % i)
    return out


def trending_for(repo, stars, snaps, today):
    """Per-card placeholder (own d7/d30 by the windows in trending.py); main() sets the section-wide ready/rank afterwards."""
    ready, rows, _ = TR.compute([{'repo': repo, 'slug': '', 'stars': stars}], snaps, today)
    return {'ready': ready, 'd7': rows[0]['d7'], 'd30': rows[0]['d30'], 'rank': None}


def make_entry(name, cand, ev, now_iso, snaps, today):
    rec, M, types = ev['rec'], ev['M'], ev['types']
    node = ev['node']
    owner = node['owner']
    repo = node['nameWithOwner']
    slug = slug_of(repo)
    inst, tools, prereq = IA.build_install(M, repo, types)
    flags, best = IA.summarize(inst)
    acc = IA.access_box(M, types, bool(cand.get('servers')))
    srv = primary_server(cand.get('servers')) or {}
    topics = rec['node'].get('topics') or []
    desc_raw = node.get('description') or srv.get('description') or ''
    nm = srv.get('title') or repo.split('/')[-1]
    activity = max([d for d in (CU.parse_ts(node.get('pushedAt')), CU.parse_ts((node.get('latestRelease') or {}).get('publishedAt'))) if d])
    srcs, seen = [], set()
    for s in cand['sources']:
        k = (s['kind'], s['ref'])
        if k not in seen: seen.add(k); srcs.append(s)
    card = {
        'slug': slug, 'repo': repo, 'name': mask(nm), 'owner': owner['login'], 'avatar': owner.get('avatarUrl'),
        'desc': mask(short(desc_raw)), 'stars': node.get('stargazerCount') or 0, 'types': types, 'tools': tools,
        'category': CA.categorize_ai(topics, repo.split('/')[-1], desc_raw), 'prerequisites': prereq,
        'latest_activity_at': activity.strftime('%Y-%m-%dT%H:%M:%SZ'), 'sources': srcs,
        'install_summary': flags, 'access': acc,
        'trending': trending_for(repo, node.get('stargazerCount') or 0, snaps, today),
    }
    detail = dict(card)
    detail.update({'repo_url': 'https://github.com/' + repo, 'homepage': node.get('homepageUrl') or None,
                   'license': (node.get('licenseInfo') or {}).get('spdxId'), 'topics': [mask(t) for t in topics],
                   'forks': node.get('forkCount') or 0, 'manifests_found': M['found'], 'install': inst,
                   'readme_excerpt_removed': True, 'best_method': best,
                   'usage': USG.build(M, repo, types, inst, srv, nm, desc_raw, rec.get('readme'),
                                     read_json(CACHE / 'usage' / (slug + '.json')), IA, IA.server_dict)})
    masked = (card['desc'] != short(desc_raw)) or (card['name'] != nm)
    return card, detail, best, masked


def pct(n, d): return round(100.0 * n / d, 1) if d else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', type=int, default=200)
    ap.add_argument('--cap', type=int, default=1500)
    ap.add_argument('--batch', type=int, default=10)
    ap.add_argument('--max-age-hours', type=float, default=20)
    ap.add_argument('--registry-max-age-hours', type=float, default=1)
    ap.add_argument('--offline', action='store_true', help='use caches only, no network')
    ap.add_argument('--max-stale-days', type=float, default=PL.MAX_STALE_DAYS, help='a repo that cannot be fetched keeps its previous data this long')
    ap.add_argument('--max-not-fresh', type=float, default=PL.MAX_NOT_FRESH_FRACTION, help='fail (exit 4, nothing written) above this share of not-fresh repos')
    ap.add_argument('--no-changelog', action='store_true')
    ap.add_argument('--history-dir', help='directory with ai-snapshot-YYYY-MM-DD.json (default data/history)')
    ap.add_argument('--with-github-trending', action='store_true',
                    help='OPT-IN (default off): read github.com/trending (2 requests max) and curate its repos as extra candidates')
    a = ap.parse_args()
    hist = pathlib.Path(a.history_dir) if a.history_dir else HIST
    CACHE.mkdir(parents=True, exist_ok=True)
    token = B.load_token()
    if not token and not a.offline:
        log('no token (GH_TOKEN or ~/.gh_token)'); return 2
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    fetcher = AIFetcher(token or '')

    registry, registry_fallback = registry_or_previous(a.registry_max_age_hours, a.offline)
    topics_res = topic_search(token, a.max_age_hours, a.offline)
    github = TR.disabled_github()
    tfile = DATA / 'trending_candidates.txt'
    if a.with_github_trending:
        if a.offline:
            github = {'enabled': True, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []}
            log('github trending: enabled but --offline, not fetched')
        else:
            B.CACHE.mkdir(parents=True, exist_ok=True)
            github = TR.get_github_trending(B.CACHE / 'github_trending.json', log=log)
            log('github trending: enabled, ok=%s' % github['ok'])
            if github['ok']: TR.write_candidates(tfile, TR.read_candidates(tfile), github)
    cands, reg_stats, topic_counts = build_candidates(registry, topics_res, TR.read_candidates(tfile))
    log('candidates (before dedupe): %d' % len(cands))

    tstats = {'seen': sum(1 for c in cands.values() if c.get('trend_only')) + reg_stats['github_trending_already_known'],
              'added': 0, 'already_known': reg_stats['github_trending_already_known'], 'rejected': {}}
    need = [c['name'] for c in cands.values() if c['stars'] is None]
    sl = star_lookup(fetcher, need, a.max_age_hours, a.offline)
    unresolved = 0
    byid = {}
    for k, c in list(cands.items()):
        if c['stars'] is None:
            r = sl.get(c['name'].lower())
            if not r:
                unresolved += 1
                if c.get('trend_only'): tstats['rejected']['not_found'] = tstats['rejected'].get('not_found', 0) + 1
                continue
            c['id'], c['stars'], c['name'] = r['id'], r['stars'], r['name']
        byid.setdefault(c['id'], []).append(c)
    merged, dup_merged = [], 0
    for cid, lst in byid.items():
        base = max(lst, key=lambda c: (c['stars'] or 0))
        base['trend_only'] = all(c.get('trend_only') for c in lst)
        for o in lst:
            if o is not base:
                dup_merged += 1
                base['sources'] += o['sources']; base['servers'] += o['servers']
        merged.append(base)
    allranked = sorted(merged, key=lambda c: (-(c['stars'] or 0), c['name'].lower()))
    ranked = [c for c in allranked if not c.get('trend_only')]
    trend_list = [c for c in allranked if c.get('trend_only')]
    both = sum(1 for c in ranked if {s['kind'] for s in c['sources']} == {'registry', 'gh_topic'})
    log('ranked unique repos: %d (unresolved registry repos %d, merged duplicates by databaseId %d)' % (len(ranked), unresolved, dup_merged))

    # ---- examine in star order
    rej = {c: 0 for c in CU.CODES}
    rej_examples = {c: [] for c in CU.CODES}
    included, examined, fetch_failed, dupes = [], 0, 0, 0
    seen_ids, fetched_names = set(), []
    reasons, stale_list, expired_list = {}, [], []
    stale_h = a.max_age_hours
    CH = 30
    pos = 0
    stop = False
    while pos < len(ranked) and not stop:
        chunk = ranked[pos:pos + CH]
        names = [c['name'] for c in chunk]
        failed = fetch_repos(fetcher, names, a.batch, a.max_age_hours, a.offline)
        jobs = skill_jobs(chunk, now)
        if not a.offline: fetch_skills(fetcher, jobs, 8)
        for c in chunk:
            pos += 1
            ev = evaluate(c['name'], c, now)
            fetched_names.append(c['name'])
            if ev['status'] in ('fetch_failed', 'missing'):
                fetch_failed += 1; reasons[c['name'].lower()] = 'fetch_failed'; continue
            if ev['age_days'] * 24 > stale_h:
                if ev['age_days'] > a.max_stale_days:
                    expired_list.append((c['name'], round(ev['age_days'], 2))); fetch_failed += 1; reasons[c['name'].lower()] = 'stale_expired'; continue
                stale_list.append((c['name'], round(ev['age_days'], 2)))
            did = ev['rec']['node']['databaseId']
            if did in seen_ids: dupes += 1; continue
            seen_ids.add(did)
            examined += 1
            if ev['status'] == 'rejected':
                rej[ev['code']] += 1; reasons[c['name'].lower()] = ev['code']
                if len(rej_examples[ev['code']]) < 5: rej_examples[ev['code']].append('%s: %s' % (c['name'], ev['detail']))
            else:
                included.append((c, ev))
            if len(included) >= a.target or examined >= a.cap:
                stop = True; break
        log('progress: examined=%d included=%d rejected=%s' % (examined, len(included), sum(rej.values())))

    n_checked = len(fetched_names)
    n_missing = fetch_failed - len(expired_list)
    fr = {'fresh': [None] * (n_checked - len(stale_list) - len(expired_list) - n_missing - dupes - 0), 'stale': stale_list, 'expired': expired_list,
          'missing': [None] * n_missing}
    guard_ok, n_bad, frac = PL.guard(n_checked, fr, a.max_not_fresh)
    fstats = PL.freshness_stats(fr, a.max_stale_days)
    log('freshness: fresh=%d stale_reused=%d stale_expired=%d missing=%d (not fresh %.1f%%)' % (
        fstats['fresh'], fstats['stale_reused'], fstats['stale_expired'], fstats['missing'], 100 * frac))
    if not a.offline and not guard_ok:
        log('GUARD: %d of %d repos are not fresh (limit %.0f%%). Nothing was written; the previous site data stays.' % (n_bad, n_checked, 100 * a.max_not_fresh))
        return 4

    # ---- github_trending candidates: same R1-R8 curation, outside the star-order target/cap, counted separately
    for i in range(0, len(trend_list), CH):
        chunk = trend_list[i:i + CH]
        fetch_repos(fetcher, [c['name'] for c in chunk], a.batch, a.max_age_hours, a.offline)
        jobs = skill_jobs(chunk, now)
        if not a.offline: fetch_skills(fetcher, jobs, 8)
        for c in chunk:
            ev = evaluate(c['name'], c, now)
            fetched_names.append(c['name'])
            if ev['status'] in ('fetch_failed', 'missing'):
                k = 'fetch_failed'
            elif ev['rec']['node']['databaseId'] in seen_ids:
                k = 'duplicate_database_id'
            else:
                seen_ids.add(ev['rec']['node']['databaseId'])
                k = ev['code'] if ev['status'] == 'rejected' else None
            if k: tstats['rejected'][k] = tstats['rejected'].get(k, 0) + 1
            else: tstats['added'] += 1; included.append((c, ev))

    # ---- build outputs
    snaps = TR.load_snapshots(hist, 'ai-')
    cards, details, best_counts, masked_n, forb_skipped = [], [], {}, 0, []
    for c, ev in included:
        card, detail, best, masked = make_entry(c['name'], c, ev, now.strftime('%Y-%m-%dT%H:%M:%SZ'), snaps, today)
        gen = {k: v for k, v in detail.items() if k not in ('name', 'desc', 'topics', 'repo', 'slug', 'owner', 'avatar', 'homepage', 'repo_url', 'sources', 'license', 'manifests_found')}
        bad = scan_forbidden(gen)
        if bad:
            forb_skipped.append({'repo': card['repo'], 'fields': bad[:3]}); continue
        masked_n += 1 if masked else 0
        cards.append(card); details.append(detail)
        best_counts[best] = best_counts.get(best, 0) + 1
    order = sorted(range(len(cards)), key=lambda i: (-cards[i]['stars'], cards[i]['repo'].lower()))
    cards = [cards[i] for i in order]; details = [details[i] for i in order]
    n = len(cards)
    ready, trows, tbase = TR.compute([{'repo': c['repo'], 'slug': c['slug'], 'stars': c['stars']} for c in cards], snaps, today)
    tranked = TR.rank_rows(trows)
    for c, r in zip(cards, trows):             # in place: the detail files share these dicts
        c['trending'].update({'ready': ready, 'd7': r['d7'], 'd30': r['d30'], 'rank': r['rank']})

    per_type = {t: sum(1 for c in cards if t in c['types']) for t in ('mcp', 'skill', 'plugin')}
    per_tool = {t: sum(1 for c in cards if t in c['tools']) for t in IA.TOOLS}
    entries_per_source = {'registry': sum(1 for c in cards if any(s['kind'] == 'registry' for s in c['sources'])),
                          'gh_topic': sum(1 for c in cards if any(s['kind'] == 'gh_topic' for s in c['sources'])),
                          'github_trending': sum(1 for c in cards if any(s['kind'] == 'github_trending' for s in c['sources']))}
    entries_per_topic = {}
    for c in cards:
        for s in {s['ref'] for s in c['sources'] if s['kind'] == 'gh_topic'}:
            entries_per_topic[s] = entries_per_topic.get(s, 0) + 1
    cost_total, queries_total = 0, 0
    if COST_LOG.exists():
        for ln in COST_LOG.read_text(encoding='utf-8').splitlines():
            try:
                r = json.loads(ln); cost_total += r.get('cost') or 0; queries_total += 1
            except Exception:
                pass
    kinds_any = {k: sum(1 for c in cards if c['install_summary'][k]) for k in IA.KINDS}
    stats = {
        'generated_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'count': n,
        'entries_per_type': per_type, 'entries_per_tool': per_tool,
        'best_method_counts': {k: best_counts.get(k, 0) for k in IA.KINDS + ['none']},
        'best_method_percent': {k: pct(best_counts.get(k, 0), n) for k in IA.KINDS + ['none']},
        'any_method_percent': {k: pct(v, n) for k, v in kinds_any.items()},
        'rejections_per_code': rej, 'rejection_examples': rej_examples,
        'examined': examined, 'included_before_word_filter': len(included), 'included': n,
        'target': a.target, 'cap': a.cap, 'ranked_unique_repos': len(ranked),
        'fetched_not_examined': max(0, len(fetched_names) - examined - fetch_failed - dupes),
        'fetch_failed': fetch_failed, 'duplicate_database_id_after_fetch': dupes,
        'forbidden_word_identifier_skipped': forb_skipped, 'masked_desc_or_name_entries': masked_n,
        'sources': {'registry': dict(reg_stats, mode=registry.get('mode'), incremental=registry.get('incremental'), records_seen=registry.get('records_seen'), pages=registry.get('pages'),
                                     skipped_records=registry.get('skipped_status'), unresolved_repos=unresolved),
                    'gh_topic_items_per_topic': topic_counts, 'candidates_unique_after_dedupe': len(ranked),
                    'duplicates_merged_by_database_id': dup_merged, 'candidates_in_both_sources': both,
                    'entries_per_source': entries_per_source, 'entries_per_topic': entries_per_topic},
        'graphql': {'points_total_all_runs': cost_total, 'queries_total_all_runs': queries_total,
                    'points_this_run': fetcher.session_cost, 'queries_this_run': fetcher.queries, 'remaining_last': fetcher.remaining},
        'categories': {k: sum(1 for c in cards if c['category'] == k) for k in CA.CATEGORY_IDS},
        'trending': {'ready': ready, 'ranked': len(tranked), 'badges': sum(1 for r in tranked if TR.has_badge(r['d7'], r['rank'], r['stars']))},
        'trending_candidates': tstats,
        'mcp_without_install_spec': sum(1 for d in details if 'mcp' in d['types'] and d['install']['claude-code']['mcp']['kind'] == 'none'),
        'decisions': DECISIONS,
    }
    stats['freshness'] = fstats
    stats['registry_fallback'] = registry_fallback
    cur = {c['repo'].lower(): {'repo': c['repo'], 'stars': c['stars']} for c in cards}
    srcmap = {c['repo'].lower(): '+'.join(sorted({s['kind'] for s in c['sources']})) for c in cards}
    if not a.no_changelog:
        PL.record_changelog(CHANGELOG, 'ai', today.isoformat(), cur, reasons, srcmap, default_reason='rank_cutoff',
                            extra={'examined': examined, 'stale_reused': fstats['stale_reused'], 'target': a.target})
    OUT.mkdir(parents=True, exist_ok=True)
    adir = OUT / 'ai'
    adir.mkdir(parents=True, exist_ok=True)
    keep = set()
    for d in details:
        B.atomic_write(adir / (d['slug'] + '.json'), B.jdump(d)); keep.add(d['slug'] + '.json')
    for f in adir.glob('*.json'):
        if f.name not in keep: f.unlink()
    B.atomic_write(OUT / 'catalog-ai.json', B.jdump({'generated_at': stats['generated_at'], 'count': n, 'entries': cards}))
    B.atomic_write(OUT / 'stats-ai.json', B.jdump(stats, indent=1))
    PL.update_meta(OUT, 'ai', stats['generated_at'])
    B.atomic_write(OUT / 'changelog-ai.json', B.jdump({'generated_at': stats['generated_at'], 'section': 'ai', 'entries': PL.published_changelog(CHANGELOG, 'ai')}))
    B.atomic_write(OUT / 'trending-ai.json', B.jdump(TR.trending_doc(tranked, ready, stats['generated_at'], snaps, tbase, github, today)))
    hist.mkdir(parents=True, exist_ok=True)
    snap = {}
    for nm in fetched_names:
        j = read_json(repo_cache(nm))
        r = (j or {}).get('rec')
        if r: snap[r['node']['nameWithOwner']] = {'stars': r['node'].get('stargazerCount') or 0}
    B.atomic_write(hist / ('ai-snapshot-%s.json' % today.isoformat()), B.jdump(snap))
    log('done: entries=%d examined=%d rejections=%s' % (n, examined, rej))
    return 0


if __name__ == '__main__':
    sys.exit(main())
