"""Releases through the REST API with conditional requests (ETag / If-None-Match).

Why REST: GraphQL POST has no conditional requests.  A 304 answer does not count against the primary rate limit and tells us the
release list did not change, so the cached copy is reused.  Download counts live inside the response body, so a repo whose assets are
being downloaded changes its ETag often: the 304 share is measured and reported (stats.releases_rest), never assumed.

Output is converted to the GraphQL node shape the builder already uses (tagName, name, isPrerelease, isDraft, publishedAt,
description, url, releaseAssets.nodes[name,size,downloadCount,downloadUrl,updatedAt]), so nothing downstream changes.
Nothing from a response is executed.  The token only travels in the Authorization header and is never stored or logged.
"""
import json, os, time, pathlib, threading, urllib.request, urllib.error, concurrent.futures as cf

API = 'https://api.github.com'
UA = 'catalog-builder'


def adapt(rel):
    """REST release object -> GraphQL-shaped release node."""
    if not isinstance(rel, dict): return None
    assets = []
    for a in sorted(rel.get('assets') or [], key=lambda x: (x or {}).get('id') or 0):      # GraphQL lists assets in id order; REST does not
        assets.append({'name': a.get('name'), 'size': a.get('size'), 'downloadCount': a.get('download_count') or 0,
                       'downloadUrl': a.get('browser_download_url'), 'updatedAt': a.get('updated_at')})
    return {'tagName': rel.get('tag_name'), 'name': rel.get('name'), 'isPrerelease': bool(rel.get('prerelease')),
            'isDraft': bool(rel.get('draft')), 'publishedAt': rel.get('published_at'), 'description': rel.get('body'),
            'url': rel.get('html_url'), 'releaseAssets': {'nodes': assets}}


def default_get(url, headers, timeout=60):
    """-> (status, headers_dict_lowercase, body_bytes).  HTTP errors are returned, not raised; network errors raise."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return f.status, {k.lower(): v for k, v in f.headers.items()}, f.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


class RestReleases:
    def __init__(self, token, cache_dir, getter=None, workers=4, per_page=15):
        self.token = token
        self.dir = pathlib.Path(cache_dir)
        self.get = getter or default_get
        self.workers = workers
        self.per_page = per_page
        self.stats = {'requests': 0, 'status_200': 0, 'status_304': 0, 'status_404': 0, 'errors': 0, 'stale_cache_used': 0, 'latest_extra_requests': 0}
        self.remaining = None
        self.reset_at = None
        self._lock = threading.Lock()

    # -- cache
    def _path(self, name): return self.dir / (name.lower().replace('/', '__') + '.json')

    def _load(self, name):
        try: return json.loads(self._path(name).read_text(encoding='utf-8'))
        except Exception: return None

    def _save(self, name, rec):
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self._path(name)
        tmp = p.with_name(p.name + '.tmp%d' % os.getpid())
        tmp.write_text(json.dumps(rec, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')
        os.replace(tmp, p)

    # -- http
    def _hdrs(self, etag=None):
        h = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': UA}
        if etag: h['If-None-Match'] = etag
        return h

    def _note(self, status, hdrs):
      with self._lock:
        self.stats['requests'] += 1
        k = 'status_%d' % status
        if k in self.stats: self.stats[k] += 1
        try:
            self.remaining = int(hdrs.get('x-ratelimit-remaining', self.remaining if self.remaining is not None else -1))
            self.reset_at = int(hdrs.get('x-ratelimit-reset', 0)) or self.reset_at
        except Exception:
            pass

    def _wait_if_low(self):
        if self.remaining is not None and 0 <= self.remaining < 50 and self.reset_at:
            time.sleep(min(max(5, self.reset_at - time.time() + 5), 3700))
            self.remaining = None

    def _conditional(self, url, etag):
        """-> ('304'|'200'|'404'|'error', body|None, etag|None)"""
        for attempt in range(3):
            self._wait_if_low()
            try:
                status, h, body = self.get(url, self._hdrs(etag))
            except Exception:
                time.sleep(1 + attempt); continue
            self._note(status, h)
            if status == 304: return '304', None, etag
            if status == 200: return '200', json.loads(body.decode('utf-8')), h.get('etag')
            if status == 404: return '404', None, None
            if status in (403, 429) and (h.get('x-ratelimit-remaining') == '0' or h.get('retry-after')):
                wait = int(h.get('retry-after') or max(5, int(h.get('x-ratelimit-reset', time.time() + 30)) - time.time() + 3))
                time.sleep(min(wait, 3700)); continue
            time.sleep(1 + attempt)
        with self._lock: self.stats['errors'] += 1
        return 'error', None, None

    # -- public
    def fetch(self, full_name, latest_tag=None):
        """full_name: canonical 'Owner/Repo' (nameWithOwner from GraphQL, so no redirect is needed).
        latest_tag: tagName of the repo's 'Latest' release (GraphQL, one cheap field), or None when it has no latest release.
        -> dict(nodes=[GraphQL-shaped releases], latest=node|None, state='200'|'304'|'stale'|'404', ok=bool)"""
        rec = self._load(full_name) or {}
        url = '%s/repos/%s/releases?per_page=%d' % (API, full_name, self.per_page)
        res, body, etag = self._conditional(url, rec.get('etag') if rec.get('list') is not None else None)
        if res == 'error':
            if rec.get('list') is not None:
                with self._lock: self.stats['stale_cache_used'] += 1
                return self._shape(rec, latest_tag, 'stale', True)
            return {'nodes': [], 'latest': None, 'state': 'error', 'ok': False}
        if res == '404':
            rec = {'etag': None, 'list': [], 'saved_at': time.time(), 'latest_extra': None}
            self._save(full_name, rec)
            return self._shape(rec, latest_tag, '404', True)
        if res == '200':
            rec = {'etag': etag, 'list': body, 'saved_at': time.time(), 'latest_extra': rec.get('latest_extra')}
        out = self._shape(rec, latest_tag, res, True)
        # 'Latest' not inside the newest 15: one extra request for exactly that tag
        if latest_tag and out['latest'] is None:
            ex = rec.get('latest_extra')
            if not (ex and ex.get('tag_name') == latest_tag):
                r2, b2, _ = self._conditional('%s/repos/%s/releases/tags/%s' % (API, full_name, urllib.request.quote(latest_tag, safe='')), None)
                with self._lock: self.stats['latest_extra_requests'] += 1
                ex = b2 if r2 == '200' else None
                rec['latest_extra'] = ex
            out['latest'] = adapt(ex) if ex else None
        self._save(full_name, rec)
        return out

    def _shape(self, rec, latest_tag, state, ok):
        nodes = [adapt(r) for r in (rec.get('list') or []) if isinstance(r, dict)]
        latest = next((n for n in nodes if latest_tag and n['tagName'] == latest_tag and not n['isDraft']), None)
        return {'nodes': nodes, 'latest': latest, 'state': state, 'ok': ok}

    def fetch_many(self, items):
        """items: [(full_name, latest_tag)] -> {full_name: result}"""
        out = {}
        with cf.ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {ex.submit(self.fetch, n, t): n for n, t in items}
            for f in cf.as_completed(futs):
                n = futs[f]
                try: out[n] = f.result()
                except Exception as e:
                    self.stats['errors'] += 1
                    out[n] = {'nodes': [], 'latest': None, 'state': 'error', 'ok': False}
        return out

    def report(self):
        s = dict(self.stats)
        ok = s['status_200'] + s['status_304']
        s['share_304'] = round(s['status_304'] / ok, 4) if ok else None
        return s
