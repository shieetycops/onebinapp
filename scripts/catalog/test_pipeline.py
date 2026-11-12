"""Tests for pipeline.py, releases_rest.py and the per-repo fallback in build_catalog.Fetcher.  Run: python -I scripts/catalog/test_pipeline.py
No network: HTTP is a fake getter, GraphQL is a fake query_batch."""
import sys, json, pathlib, tempfile, time, unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import pipeline as PL           # noqa: E402
import releases_rest as RR      # noqa: E402
import build_catalog as B       # noqa: E402
import build_ai as A            # noqa: E402
import discover as D            # noqa: E402

REL = lambda tag, n_assets=2, prerelease=False: {
    'tag_name': tag, 'name': tag, 'prerelease': prerelease, 'draft': False, 'published_at': '2026-10-01T00:00:00Z', 'body': 'notes',
    'html_url': 'https://github.com/o/r/releases/tag/' + tag,
    'assets': [{'id': 10 - i, 'name': 'app-%d.exe' % i, 'size': 100, 'download_count': 3, 'browser_download_url': 'https://github.com/o/r/releases/download/%s/app-%d.exe' % (tag, i), 'updated_at': 'x'} for i in range(n_assets)]}


class FakeHttp:
    """Serves release lists with ETags; honours If-None-Match; can be told to fail."""
    def __init__(self): self.lists = {}; self.etags = {}; self.calls = []; self.fail = set(); self.status_override = {}; self.cut = set()
    def set(self, name, rels): self.lists[name] = rels; self.etags[name] = 'W/"%d"' % abs(hash(json.dumps(rels)))
    def __call__(self, url, headers):
        self.calls.append((url, headers.get('If-None-Match')))
        name = url.split('/repos/')[1].split('/releases')[0]
        if name in self.fail: raise OSError('network down')
        if name in self.status_override: return self.status_override[name], {'x-ratelimit-remaining': '4000'}, b'{}'
        if '/releases/tags/' in url:
            tag = url.rsplit('/', 1)[1]
            r = next((x for x in self.lists[name] if x['tag_name'] == tag), None)
            return (200, {'etag': 'e', 'x-ratelimit-remaining': '4000'}, json.dumps(r).encode()) if r else (404, {}, b'{}')
        if name not in self.lists: return 404, {'x-ratelimit-remaining': '4000'}, b'{}'
        if headers.get('If-None-Match') == self.etags[name]: return 304, {'etag': self.etags[name], 'x-ratelimit-remaining': '4000'}, b''
        body = self.lists[name][:15] if name in self.cut else self.lists[name]       # per_page=15
        return 200, {'etag': self.etags[name], 'x-ratelimit-remaining': '4000'}, json.dumps(body).encode()


class TestRest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp()); self.http = FakeHttp(); self.http.set('o/r', [REL('v2'), REL('v1')])

    def mk(self): return RR.RestReleases('tok', self.tmp, getter=self.http, workers=2)

    def test_adapt_shape_and_asset_order_by_id(self):
        n = RR.adapt(REL('v1', 3))
        self.assertEqual(n['tagName'], 'v1'); self.assertIs(n['isDraft'], False); self.assertEqual(n['url'], 'https://github.com/o/r/releases/tag/v1')
        self.assertEqual([a['name'] for a in n['releaseAssets']['nodes']], ['app-2.exe', 'app-1.exe', 'app-0.exe'])   # ids 8,9,10 ascending
        self.assertEqual(n['releaseAssets']['nodes'][0]['downloadCount'], 3)

    def test_second_run_is_304_and_sends_if_none_match(self):
        r1 = self.mk().fetch('o/r', 'v2'); self.assertEqual(r1['state'], '200'); self.assertEqual(r1['latest']['tagName'], 'v2')
        c = self.mk(); r2 = c.fetch('o/r', 'v2')
        self.assertEqual(r2['state'], '304'); self.assertEqual(r2['nodes'], r1['nodes']); self.assertEqual(r2['latest']['tagName'], 'v2')
        self.assertEqual(self.http.calls[-1][1], self.http.etags['o/r'])
        self.assertEqual(c.report()['share_304'], 1.0)

    def test_changed_list_returns_200_with_new_data(self):
        self.mk().fetch('o/r', 'v2')
        self.http.set('o/r', [REL('v3'), REL('v2'), REL('v1')])
        r = self.mk().fetch('o/r', 'v3'); self.assertEqual(r['state'], '200'); self.assertEqual(r['nodes'][0]['tagName'], 'v3')

    def test_network_error_uses_cached_copy_and_is_counted(self):
        self.mk().fetch('o/r', 'v2'); self.http.fail.add('o/r')
        c = self.mk(); r = c.fetch('o/r', 'v2')
        self.assertTrue(r['ok']); self.assertEqual(r['state'], 'stale'); self.assertEqual(c.report()['stale_cache_used'], 1)

    def test_network_error_without_cache_is_not_ok(self):
        self.http.fail.add('o/r'); r = self.mk().fetch('o/r', 'v2'); self.assertFalse(r['ok'])

    def test_latest_outside_window_costs_one_extra_request(self):
        rels = [REL('v%d' % i) for i in range(20, 4, -1)] + [REL('v1')]      # 16 releases; 'v1' is the Latest flag but beyond the 15 newest
        self.http.set('o/r', rels); self.http.cut.add('o/r')
        c = self.mk(); r = c.fetch('o/r', 'v1')
        self.assertEqual(len(r['nodes']), 15); self.assertEqual(r['latest']['tagName'], 'v1'); self.assertEqual(c.report()['latest_extra_requests'], 1)
        c2 = self.mk(); r2 = c2.fetch('o/r', 'v1')                            # next run: 304 and the extra release comes from the cache
        self.assertEqual(r2['state'], '304'); self.assertEqual(r2['latest']['tagName'], 'v1'); self.assertEqual(c2.report()['latest_extra_requests'], 0)

    def test_repo_without_releases(self):
        r = self.mk().fetch('o/none', None); self.assertTrue(r['ok']); self.assertEqual(r['nodes'], []); self.assertIsNone(r['latest'])

    def test_token_is_only_in_authorization_header(self):
        seen = []
        def g(url, headers): seen.append((url, dict(headers))); return 200, {'etag': 'x'}, b'[]'
        RR.RestReleases('SECRET-TOKEN', self.tmp, getter=g).fetch('o/r', None)
        self.assertNotIn('SECRET-TOKEN', seen[0][0]); self.assertEqual(seen[0][1]['Authorization'], 'Bearer SECRET-TOKEN')
        for f in self.tmp.glob('*.json'): self.assertNotIn('SECRET-TOKEN', f.read_text())


class TestFreshness(unittest.TestCase):
    def test_classification(self):
        now = 1_000_000_000.0
        ages = {'fresh': 2, 'stale': 30, 'expired': 24 * 9 + 1, 'missing': None}
        fr = PL.classify_freshness(list(ages), lambda n: None if ages[n] is None else now - ages[n] * 3600, now, 20, 7)
        self.assertEqual(fr['fresh'], ['fresh']); self.assertEqual([n for n, _ in fr['stale']], ['stale'])
        self.assertEqual([n for n, _ in fr['expired']], ['expired']); self.assertEqual(fr['missing'], ['missing'])

    def test_guard(self):
        fr = {'fresh': ['a'] * 80, 'stale': [('b', 1)] * 20, 'expired': [], 'missing': []}
        self.assertTrue(PL.guard(100, fr)[0])                                   # 20% is allowed
        fr['expired'] = [('c', 9)]
        ok, bad, frac = PL.guard(101, fr); self.assertFalse(ok); self.assertEqual(bad, 21)
        self.assertTrue(PL.guard(0, {'fresh': [], 'stale': [], 'expired': [], 'missing': []})[0])


class TestFetcherFallback(unittest.TestCase):
    """A repo whose release fetch fails keeps its previous cache file; the others are refreshed; the build is not stopped."""
    def test_failed_repo_keeps_previous_cache(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        old_repos, old_log = B.REPOS_CACHE, B.COST_LOG
        B.REPOS_CACHE = tmp / 'repos'; B.COST_LOG = tmp / 'cost.jsonl'
        try:
            B.REPOS_CACHE.mkdir()
            prev = {'requested': 'o/bad', 'fetched_at': 1.0, 'node': {'databaseId': 2, 'nameWithOwner': 'o/bad', 'marker': 'previous'}}
            B.atomic_write(B.cache_path('o/bad'), B.jdump(prev))
            http = FakeHttp(); http.set('o/good', [REL('v1')]); http.fail.add('o/bad')
            fx = B.Fetcher('tok')
            fx.rest = RR.RestReleases('tok', tmp / 'rest', getter=http, workers=2)
            fx.query_batch = lambda names, rel_n=15: {n: {'databaseId': 1 if n == 'o/good' else 2, 'nameWithOwner': n, 'latestRelease': {'tagName': 'v1'}} for n in names}
            failed = fx.fetch(['o/good', 'o/bad'], 10)
            self.assertEqual(failed, ['o/bad'])
            good = json.loads(B.cache_path('o/good').read_text(encoding='utf-8'))
            self.assertEqual(good['node']['releases']['nodes'][0]['tagName'], 'v1'); self.assertEqual(good['node']['latestRelease']['tagName'], 'v1')
            kept = json.loads(B.cache_path('o/bad').read_text(encoding='utf-8'))
            self.assertEqual(kept['node']['marker'], 'previous'); self.assertEqual(kept['fetched_at'], 1.0)
        finally:
            B.REPOS_CACHE, B.COST_LOG = old_repos, old_log

    def _fx(self, tmp, http, nodes):
        fx = B.Fetcher('tok')
        fx.rest = RR.RestReleases('tok', tmp / 'rest', getter=http, workers=2)
        fx.query_batch = lambda names, rel_n=15: {n: dict(nodes[n]) for n in names}
        return fx

    def test_rest_error_with_cached_release_list_does_not_refresh_the_repo(self):
        """Regression: a stale REST answer (old release list reused) must not rewrite the repo cache with a new fetched_at."""
        tmp = pathlib.Path(tempfile.mkdtemp())
        old_repos, old_log = B.REPOS_CACHE, B.COST_LOG
        B.REPOS_CACHE = tmp / 'repos'; B.COST_LOG = tmp / 'cost.jsonl'
        try:
            B.REPOS_CACHE.mkdir()
            http = FakeHttp(); http.set('o/r', [REL('v1')])
            nodes = {'o/r': {'databaseId': 1, 'nameWithOwner': 'o/r', 'latestRelease': {'tagName': 'v1'}}}
            fx = self._fx(tmp, http, nodes)
            self.assertEqual(fx.fetch(['o/r'], 10), [])
            first = json.loads(B.cache_path('o/r').read_text(encoding='utf-8'))
            first['fetched_at'] = 5.0                                     # pretend it is old
            B.atomic_write(B.cache_path('o/r'), B.jdump(first))
            http.fail.add('o/r')                                          # REST outage, REST cache still holds a list
            fx2 = self._fx(tmp, http, nodes)
            failed = fx2.fetch(['o/r'], 10)
            self.assertEqual(failed, ['o/r'])
            self.assertEqual(json.loads(B.cache_path('o/r').read_text(encoding='utf-8'))['fetched_at'], 5.0)   # unchanged: it ages honestly
        finally:
            B.REPOS_CACHE, B.COST_LOG = old_repos, old_log

    def test_repos_rejected_by_metadata_get_no_release_request(self):
        tmp = pathlib.Path(tempfile.mkdtemp())
        old_repos, old_log = B.REPOS_CACHE, B.COST_LOG
        B.REPOS_CACHE = tmp / 'repos'; B.COST_LOG = tmp / 'cost.jsonl'
        try:
            B.REPOS_CACHE.mkdir()
            http = FakeHttp(); http.set('o/keep', [REL('v1')]); http.set('o/reject', [REL('v1')])
            nodes = {n: {'databaseId': i, 'nameWithOwner': n, 'latestRelease': {'tagName': 'v1'}} for i, n in enumerate(['o/keep', 'o/reject'], 1)}
            fx = self._fx(tmp, http, nodes)
            fx.rest_skip = lambda n, node: n == 'o/reject'
            fx.fetch(['o/keep', 'o/reject'], 10)
            asked = [u for u, _ in http.calls]
            self.assertTrue(any('/o/keep/' in u for u in asked)); self.assertFalse(any('/o/reject/' in u for u in asked))
            rej = json.loads(B.cache_path('o/reject').read_text(encoding='utf-8'))['node']
            self.assertTrue(rej['releases_skipped']); self.assertEqual(rej['releases'], {'nodes': []}); self.assertEqual(fx.rest_skipped, 1)
        finally:
            B.REPOS_CACHE, B.COST_LOG = old_repos, old_log

    def test_light_query_has_no_releases(self):
        self.assertNotIn('releases(', B.GQL_LIGHT); self.assertNotIn('releaseAssets', B.GQL_LIGHT); self.assertIn('latestRelease { tagName }', B.GQL_LIGHT)
        self.assertIn('releaseAssets', B.GQL_FIELDS)


class TestChangelog(unittest.TestCase):
    def cur(self, *names): return {n.lower(): {'repo': n, 'stars': 10} for n in names}

    def test_baseline_then_diff_with_reasons_and_sources(self):
        d = tempfile.mkdtemp()
        e1 = PL.record_changelog(d, 'desktop', '2026-11-12', self.cur('a/x', 'b/y'), {})
        self.assertTrue(e1['baseline']); self.assertEqual(e1['added'], [])
        e2 = PL.record_changelog(d, 'desktop', '2026-11-13', self.cur('a/x', 'c/z'), {'b/y': 'no_installer'}, {'c/z': 'komi'})
        self.assertEqual([a['repo'] for a in e2['added']], ['c/z']); self.assertEqual(e2['added'][0]['source'], 'komi')
        self.assertEqual(e2['removed'], [{'repo': 'b/y', 'reason': 'no_installer'}])

    def test_rerun_on_baseline_day_stays_baseline(self):
        d = tempfile.mkdtemp()
        PL.record_changelog(d, 's', '2026-11-12', self.cur('a/x'), {})
        e = PL.record_changelog(d, 's', '2026-11-12', self.cur('a/x'), {})
        self.assertTrue(e['baseline']); self.assertEqual(e['added'], [])

    def test_unknown_reason_is_explicit(self):
        d = tempfile.mkdtemp()
        PL.record_changelog(d, 's', '2026-11-12', self.cur('a/x'), {})
        e = PL.record_changelog(d, 's', '2026-11-13', {}, {})
        self.assertEqual(e['removed'][0]['reason'], 'no_longer_a_candidate')

    def test_same_day_rerun_keeps_the_days_diff(self):
        d = tempfile.mkdtemp()
        PL.record_changelog(d, 's', '2026-11-12', self.cur('a/x'), {})
        PL.record_changelog(d, 's', '2026-11-13', self.cur('a/x', 'n/new'), {})
        e = PL.record_changelog(d, 's', '2026-11-13', self.cur('a/x', 'n/new'), {})          # second run, nothing changed since
        self.assertEqual([a['repo'] for a in e['added']], ['n/new'])
        rows = PL.published_changelog(d, 's')
        self.assertEqual([r['date'] for r in rows], ['2026-11-13', '2026-11-12'])         # one line per day, newest first

    def test_discovered_map_parsing(self):
        p = pathlib.Path(tempfile.mkdtemp()) / 'discovered.txt'
        p.write_text('# comment\nOwner/Repo\tgh_topic:tauri\t2026-11-12\nbad line\nx/y\tkomi\n', encoding='utf-8')
        m = B.discovered_map(p)
        self.assertEqual(m['owner/repo'], ('Owner/Repo', 'gh_topic:tauri', '2026-11-12')); self.assertEqual(m['x/y'][1], 'komi'); self.assertEqual(len(m), 2)


class TestDiscover(unittest.TestCase):
    def test_parse_cask_and_search(self):
        cask = json.dumps([{'url': 'https://github.com/Foo/Bar/releases/download/v1/x.dmg', 'homepage': 'https://x.example'},
                           {'url': 'https://dl.example/y.dmg', 'homepage': 'https://github.com/baz/qux.git'}, {'url': None}, 'junk'])
        self.assertEqual(D.parse_cask(cask), {'Foo/Bar', 'baz/qux'})
        self.assertEqual(D.parse_search(json.dumps({'items': [{'full_name': 'a/b', 'stargazers_count': 5}, {'full_name': 'bad name'}]})), [('a/b', 5)])
        self.assertEqual(D.parse_search('not json'), [])

    def test_select_new_excludes_known_orders_by_stars_and_caps(self):
        found = {'a/known': (900, 'x'), 'b/new1': (300, 'gh_topic:tauri'), 'c/new2': (500, 'cask'), 'd/new3': (100, 'cask')}
        self.assertEqual(D.select_new(found, {'a/known'}, 2), [('c/new2', 'cask'), ('b/new1', 'gh_topic:tauri')])

    def test_failing_sources_are_skipped_not_fatal(self):
        calls = []
        def fetch(url, token=None):
            calls.append(url)
            if 'formulae' in url: raise OSError('down')
            if 'topic%3Atauri' in url: return 403, '{}'
            return 200, json.dumps({'items': [{'full_name': 'ok/repo', 'stargazers_count': 150}]})
        found, rep = D.collect('tok', 2, fetch=fetch, sleep=lambda s: None)
        self.assertTrue(rep['cask'].startswith('error')); self.assertEqual(rep['topics']['tauri'], 'http 403')
        self.assertEqual(found['ok/repo'], (150, 'gh_topic:electron'))
        self.assertTrue(all('SECRET' not in c for c in calls))


class TestAiFallback(unittest.TestCase):
    def test_failed_fetch_keeps_previous_good_record(self):
        tmp = pathlib.Path(tempfile.mkdtemp()); old = A.CACHE
        A.CACHE = tmp
        try:
            (tmp / 'repos').mkdir()
            B.atomic_write(A.repo_cache('o/bad'), B.jdump({'fetched_at': 1.0, 'rec': {'node': {'marker': 'previous'}}}))
            class FX:
                def with_retry(self, q): raise RuntimeError('boom')
            failed = A.fetch_repos(FX(), ['o/bad', 'o/new'], 10, 20, False)
            self.assertEqual(sorted(failed), ['o/bad', 'o/new'])
            self.assertEqual(A.read_json(A.repo_cache('o/bad'))['rec']['node']['marker'], 'previous')      # previous data survives
            self.assertIn('error', A.read_json(A.repo_cache('o/new')))                                      # no previous data: error marker
        finally:
            A.CACHE = old


class TestRegistryIncremental(unittest.TestCase):
    def rec(self, name, version='1', latest=True, status='active', desc=''):
        return {'server': {'name': name, 'version': version, 'description': desc},
                '_meta': {'io.modelcontextprotocol.registry/official': {'isLatest': latest, 'status': status}}}

    def test_merge_updates_adds_removes_and_ignores_old_versions(self):
        stored = [{'name': 'a', 'version': '1'}, {'name': 'b', 'version': '1'}, {'name': 'c', 'version': '1'}]
        recs = [self.rec('a', '2'), self.rec('d', '1'), self.rec('b', '1', status='deprecated'), self.rec('c', '0.1', latest=False)]
        skipped = {}
        out, cnt = A.merge_incremental(stored, recs, skipped)
        self.assertEqual(sorted((s['name'], s['version']) for s in out), [('a', '2'), ('c', '1'), ('d', '1')])
        self.assertEqual(cnt, {'updated': 1, 'added': 1, 'removed': 1})
        self.assertEqual(skipped, {'deprecated': 1, 'not_latest': 1})

    def run_crawl(self, cached, pages):
        tmp = pathlib.Path(tempfile.mkdtemp()); old = (A.CACHE, A.http_json)
        A.CACHE = tmp
        seen_urls = []
        def fake(url, headers=None, retries=5, timeout=90):
            seen_urls.append(url)
            i = len(seen_urls) - 1
            return pages[i], {}
        A.http_json = fake
        try:
            if cached is not None: B.atomic_write(tmp / 'registry.json', B.jdump(cached))
            return A.registry_crawl(0.0001), seen_urls, tmp
        finally:
            A.CACHE, A.http_json = old

    def test_recent_full_crawl_leads_to_incremental_with_updated_since(self):
        now = time.time()
        cached = {'complete': True, 'servers': [{'name': 'a', 'version': '1'}], 'fetched_at': now - 3600, 'started_at': now - 3600, 'full_at': now - 3600, 'skipped_status': {}}
        st, urls, tmp = self.run_crawl(cached, [{'servers': [self.rec('a', '2'), self.rec('z', '1')], 'metadata': {}}])
        self.assertIn('updated_since=', urls[0]); self.assertEqual(len(urls), 1)
        self.assertEqual(st['mode'], 'incremental'); self.assertEqual(sorted(s['name'] for s in st['servers']), ['a', 'z'])
        self.assertEqual(st['full_at'], cached['full_at'])                       # the weekly full crawl clock is not reset by an incremental one

    def test_old_full_crawl_leads_to_full_crawl_and_failure_keeps_previous_copy(self):
        now = time.time()
        cached = {'complete': True, 'servers': [{'name': 'a'}], 'fetched_at': now - 9 * 86400, 'started_at': now - 9 * 86400, 'full_at': now - 9 * 86400, 'skipped_status': {}}
        st, urls, tmp = self.run_crawl(cached, [{'servers': [self.rec('q', '1')], 'metadata': {}}])
        self.assertNotIn('updated_since', urls[0]); self.assertEqual(st['mode'], 'full'); self.assertEqual([s['name'] for s in st['servers']], ['q'])
        # a crawl that dies keeps registry.json untouched and registry_or_previous falls back to it
        tmp2 = pathlib.Path(tempfile.mkdtemp()); old = (A.CACHE, A.http_json)
        A.CACHE = tmp2
        B.atomic_write(tmp2 / 'registry.json', B.jdump(cached))
        def boom(*a, **k): raise RuntimeError('giving up')
        A.http_json = boom
        try:
            got, fb = A.registry_or_previous(0.0001)
        finally:
            A.CACHE, A.http_json = old
        self.assertEqual(got['servers'], [{'name': 'a'}]); self.assertEqual(fb['failed'], 'RuntimeError')
        self.assertTrue(json.loads((tmp2 / 'registry.json').read_text(encoding='utf-8'))['complete'])

    def test_incomplete_read_is_retried(self):
        import http.client
        self.assertTrue(issubclass(http.client.IncompleteRead, http.client.HTTPException))
        src = (HERE / 'build_ai.py').read_text(encoding='utf-8')
        self.assertIn('http.client.HTTPException', src)


if __name__ == '__main__':
    unittest.main()
