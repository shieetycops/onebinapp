"""Run: python -I scripts/catalog/test_trending.py   (stdlib unittest; no network, synthetic snapshots in temp dirs)
Covers SPEC_TRENDING.md: windows/ready/d7/d30, rank + ties, badge, github.com/trending parser + failure handling + opt-in,
and an end-to-end run of both builders (cached/offline mode, temp dirs) including the github_trending candidate curation path."""
import sys, json, pathlib, unittest, tempfile, io, time, datetime, contextlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import trending as TR
import build_catalog as B
import build_ai as BA

TODAY = datetime.date(2026, 11, 12)
BANNED_A = 'sa' + 'fe'


def day(n):
    return TODAY - datetime.timedelta(days=n)


def write_snaps(d, spec, prefix=''):
    """spec: {age_days: {repo: stars}}"""
    for age, repos in spec.items():
        (pathlib.Path(d) / ('%ssnapshot-%s.json' % (prefix, day(age).isoformat()))).write_text(
            json.dumps({k: {'stars': v, 'downloads': 1} for k, v in repos.items()}), encoding='utf-8')


def rows(**stars):
    return [{'repo': k.replace('__', '/'), 'slug': k.replace('__', '--'), 'stars': v} for k, v in stars.items()]


class Windows(unittest.TestCase):
    def snaps(self, spec):
        with tempfile.TemporaryDirectory() as d:
            write_snaps(d, spec)
            return TR.load_snapshots(d)

    def test_not_ready_below_six_days(self):
        s = self.snaps({5: {'a/b': 10}, 1: {'a/b': 12}})
        ready, out, base = TR.compute(rows(a__b=20), s, TODAY)
        self.assertFalse(ready)
        self.assertIsNone(out[0]['d7']); self.assertIsNone(out[0]['d30'])
        self.assertEqual(base, {7: None, 30: None})
        # no snapshots at all
        ready, out, _ = TR.compute(rows(a__b=20), {}, TODAY)
        self.assertFalse(ready); self.assertIsNone(out[0]['d7'])

    def test_d7_from_seven_day_old_snapshot_and_d30_null(self):
        s = self.snaps({7: {'a/b': 10}})
        ready, out, base = TR.compute(rows(a__b=25), s, TODAY)
        self.assertTrue(ready)
        self.assertEqual(out[0]['d7'], 15)
        self.assertIsNone(out[0]['d30'])            # never 0 when there is no 27-33 day snapshot
        self.assertEqual(base[7], day(7))

    def test_d30_and_d7_together(self):
        s = self.snaps({30: {'a/b': 100}, 7: {'a/b': 130}})
        _, out, _ = TR.compute(rows(a__b=150), s, TODAY)
        self.assertEqual((out[0]['d7'], out[0]['d30']), (20, 50))

    def test_window_tolerance_edges(self):
        for age, ok in ((5, False), (6, True), (7, True), (9, True), (10, False)):
            s = self.snaps({age: {'a/b': 1}})
            self.assertEqual(TR.pick_baseline(s, TODAY, 7) is not None, ok, 'd7 age %d' % age)
        for age, ok in ((26, False), (27, True), (30, True), (33, True), (34, False)):
            s = self.snaps({age: {'a/b': 1}})
            self.assertEqual(TR.pick_baseline(s, TODAY, 30) is not None, ok, 'd30 age %d' % age)

    def test_closest_wins_and_ties_take_older(self):
        s = self.snaps({6: {'a/b': 1}, 8: {'a/b': 1}, 9: {'a/b': 1}})
        self.assertEqual(TR.pick_baseline(s, TODAY, 7), day(8))      # 6 and 8 are both 1 away: older one
        s = self.snaps({7: {'a/b': 1}, 8: {'a/b': 1}})
        self.assertEqual(TR.pick_baseline(s, TODAY, 7), day(7))
        s = self.snaps({29: {'a/b': 1}, 33: {'a/b': 1}})
        self.assertEqual(TR.pick_baseline(s, TODAY, 30), day(29))

    def test_repo_missing_from_snapshot_is_null_and_todays_snapshot_ignored(self):
        s = self.snaps({7: {'other/x': 5}, 0: {'a/b': 1}})
        ready, out, _ = TR.compute(rows(a__b=25), s, TODAY)
        self.assertFalse(ready)                      # snapshot of today (age 0) is not a baseline; a/b absent from the 7-day one
        self.assertIsNone(out[0]['d7'])

    def test_snapshot_prefixes_are_separate(self):
        with tempfile.TemporaryDirectory() as d:
            write_snaps(d, {7: {'a/b': 1}})
            write_snaps(d, {8: {'a/b': 1}}, prefix='ai-')
            (pathlib.Path(d) / 'snapshot-garbage.json').write_text('{', encoding='utf-8')
            self.assertEqual(list(TR.load_snapshots(d)), [day(7)])
            self.assertEqual(list(TR.load_snapshots(d, 'ai-')), [day(8)])


class Ranking(unittest.TestCase):
    def mk(self, spec):
        return [{'repo': n, 'slug': n.replace('/', '--'), 'stars': st, 'd7': d7, 'd30': d30} for n, st, d7, d30 in spec]

    def test_order_ties_and_null_exclusion(self):
        r = self.mk([('a/a', 1000, 10, 50), ('b/b', 500, 30, None), ('c/c', 900, 10, 80), ('d/d', 100, 10, 80), ('e/e', 50, None, None),
                     ('f/f', 70, 0, 3), ('g/g', 70, -4, None), ('h/h', 5000, 10, 80)])
        ranked = TR.rank_rows(r)
        self.assertEqual([x['repo'] for x in ranked], ['b/b', 'h/h', 'c/c', 'd/d', 'a/a'])
        self.assertEqual([x['rank'] for x in ranked], [1, 2, 3, 4, 5])
        by = {x['repo']: x for x in r}
        for k in ('e/e', 'f/f', 'g/g'): self.assertIsNone(by[k]['rank'])

    def test_d30_none_sorts_after_numbers(self):
        r = self.mk([('a/a', 10, 7, None), ('b/b', 10, 7, -5)])
        self.assertEqual([x['repo'] for x in TR.rank_rows(r)], ['b/b', 'a/a'])

    def test_top_50(self):
        r = self.mk([('o/r%d' % i, 100, 1000 - i, None) for i in range(80)])
        ranked = TR.rank_rows(r)
        self.assertEqual(len(ranked), 50)
        self.assertEqual(sum(1 for x in r if x['rank'] is not None), 50)
        self.assertEqual(ranked[0]['repo'], 'o/r0'); self.assertEqual(ranked[-1]['rank'], 50)

    def test_badge_threshold(self):
        self.assertTrue(TR.has_badge(5, 1, 100))         # max(5, 1) = 5
        self.assertFalse(TR.has_badge(4, 1, 100))
        self.assertFalse(TR.has_badge(9, 1, 1000))       # 1% of 1000 = 10
        self.assertTrue(TR.has_badge(10, 1, 1000))
        self.assertFalse(TR.has_badge(500, None, 10))    # not ranked => never
        self.assertFalse(TR.has_badge(None, 1, 10))

    def test_doc_shape(self):
        r = self.mk([('a/a', 1000, 20, 50)])
        ranked = TR.rank_rows(r)
        doc = TR.trending_doc(ranked, True, '2026-11-12T00:00:00Z', {day(7): {}}, {7: day(7), 30: None}, TR.disabled_github(), TODAY)
        self.assertEqual(doc['items'], [{'slug': 'a--a', 'd7': 20, 'd30': 50, 'rank': 1}])
        self.assertEqual(doc['window_days'], {'d7': 7, 'd30': 30}); self.assertEqual(doc['sources_used'], ['stars_history'])
        self.assertEqual(doc['github_trending'], {'enabled': False, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []})
        self.assertEqual(doc['badges'], 1)
        gh = {'enabled': True, 'ok': True, 'fetched_at': 'x', 'daily': ['a/b'], 'weekly': []}
        self.assertEqual(TR.trending_doc(ranked, True, 'g', {}, {7: None, 30: None}, gh, TODAY)['sources_used'], ['stars_history', 'github_trending'])
        gh['ok'] = False
        self.assertEqual(TR.trending_doc(ranked, True, 'g', {}, {7: None, 30: None}, gh, TODAY)['sources_used'], ['stars_history'])


class FakeResp:
    def __init__(self, text): self.b = text.encode('utf-8')
    def read(self): return self.b
    def __enter__(self): return self
    def __exit__(self, *a): return False


class GithubTrending(unittest.TestCase):
    HTML = (HERE / 'fixtures' / 'github_trending_sample.html').read_text(encoding='utf-8')

    def test_parser_on_saved_fixture(self):
        self.assertEqual(TR.parse_trending_html(self.HTML), ['acme/first-app', 'Some-Org/Lib.Thing'])

    def test_parser_tolerant(self):
        for bad in ('', None, '<html>layout changed</html>', '<article><h2>no link</h2></article>', '<article', 'x' * 10000):
            self.assertEqual(TR.parse_trending_html(bad), [])

    def test_success_two_requests_user_agent_and_forbidden_names_dropped(self):
        calls = []
        page = self.HTML.replace('</div>\n<a href="/sponsors', '<article><h2><a href="/x/%s-box">y</a></h2></article></div>\n<a href="/sponsors' % BANNED_A)

        def opener(req, timeout=None):
            calls.append((req.full_url, req.get_header('User-agent')))
            return FakeResp(page)
        with tempfile.TemporaryDirectory() as d:
            cache = pathlib.Path(d) / 'gt.json'
            res = TR.get_github_trending(cache, opener=opener, log=lambda *a: None)
            self.assertTrue(res['ok']); self.assertTrue(res['enabled'])
            self.assertEqual(len(calls), 2)
            self.assertEqual(sorted(u for u, _ in calls), sorted(TR.GH_TRENDING.values()))
            self.assertTrue(all('jembatan-rilis' in ua for _, ua in calls))
            self.assertEqual(res['daily'], ['acme/first-app', 'Some-Org/Lib.Thing'])
            self.assertEqual(res['dropped_forbidden_word'], 2)
            # second call within the cache window: no request
            res2 = TR.get_github_trending(cache, opener=opener, log=lambda *a: None)
            self.assertTrue(res2['ok']); self.assertEqual(len(calls), 2)

    def test_failure_never_raises_and_retries_once(self):
        calls = []

        def opener(req, timeout=None):
            calls.append(req.full_url); raise OSError('boom')
        res = TR.get_github_trending(None, opener=opener, log=lambda *a: None, sleep=lambda s: None)
        self.assertEqual((res['enabled'], res['ok'], res['daily'], res['weekly'], res['fetched_at']), (True, False, [], [], None))
        self.assertEqual(len(calls), 2)              # daily: 1 request + 1 retry uses the whole budget; weekly not tried

    def test_request_budget_is_two_even_with_retry(self):
        calls = []

        def opener(req, timeout=None):
            calls.append(req.full_url)
            if len(calls) == 1: raise OSError('first fails')
            return FakeResp(self.HTML)
        res = TR.get_github_trending(None, opener=opener, log=lambda *a: None, sleep=lambda s: None)
        self.assertEqual(len(calls), 2)                  # daily failed once, retry used the 2nd request, weekly never requested
        self.assertEqual(calls, [TR.GH_TRENDING['daily']] * 2)
        self.assertFalse(res['ok']); self.assertEqual((res['daily'], res['weekly']), ([], []))

    def test_daily_ok_weekly_fails_gives_empty_failure(self):
        calls = []

        def opener(req, timeout=None):
            calls.append(req.full_url)
            if 'weekly' in req.full_url: raise OSError('weekly fails')
            return FakeResp(self.HTML)
        res = TR.get_github_trending(None, opener=opener, log=lambda *a: None, sleep=lambda s: None)
        self.assertEqual(len(calls), 2)
        self.assertFalse(res['ok']); self.assertEqual((res['daily'], res['weekly'], res['fetched_at']), ([], [], None))

    def test_unparsable_page_is_failure(self):
        res = TR.get_github_trending(None, opener=lambda req, timeout=None: FakeResp('<html>nothing</html>'), log=lambda *a: None)
        self.assertFalse(res['ok'])

    def test_candidates_file_union(self):
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / 'trending_candidates.txt'
            TR.write_candidates(f, {}, {'daily': ['a/b', 'c/d'], 'weekly': ['A/B']})
            got = TR.read_candidates(f)
            self.assertEqual(got, {'a/b': ['github_trending:daily', 'github_trending:weekly'], 'c/d': ['github_trending:daily']})
            TR.write_candidates(f, got, {'daily': ['e/f'], 'weekly': []})
            self.assertEqual(sorted(TR.read_candidates(f)), ['a/b', 'c/d', 'e/f'])


# ---------------------------------------------------------------- end to end (cached/offline, temp dirs)
def fresh_iso(days_ago):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago)).strftime('%Y-%m-%dT%H:%M:%SZ')


def real_today():
    return datetime.datetime.now(datetime.timezone.utc).date()


def snap_spec(repos_by_age, prefix=''):
    return {(real_today() - datetime.timedelta(days=a)): v for a, v in repos_by_age.items()}


def write_snaps_real(d, repos_by_age, prefix=''):
    for date, repos in snap_spec(repos_by_age).items():
        (pathlib.Path(d) / ('%ssnapshot-%s.json' % (prefix, date.isoformat()))).write_text(
            json.dumps({k: {'stars': v, 'downloads': 1} for k, v in repos.items()}), encoding='utf-8')


def desktop_node(dbid, nwo, desc, stars):
    rel = {'tagName': 'v1', 'name': 'v1', 'isPrerelease': False, 'isDraft': False, 'publishedAt': fresh_iso(3), 'description': 'n', 'url': 'u-' + nwo,
           'releaseAssets': {'nodes': [{'name': nwo.split('/')[1] + '-Setup.exe', 'size': 1, 'downloadCount': 1, 'downloadUrl': 'https://x/' + nwo, 'updatedAt': ''}]}}
    return {'databaseId': dbid, 'nameWithOwner': nwo, 'description': desc, 'stargazerCount': stars, 'forkCount': 0, 'isFork': False,
            'isArchived': False, 'isDisabled': False, 'owner': {'login': nwo.split('/')[0], 'avatarUrl': 'https://a'},
            'repositoryTopics': {'nodes': []}, 'licenseInfo': {'spdxId': 'MIT'}, 'homepageUrl': None, 'pushedAt': fresh_iso(3),
            'latestRelease': rel, 'releases': {'nodes': [rel]}}


class Patched:
    """Temporarily point module globals at a temp tree and stub the network-facing functions."""
    def __init__(self, mod_attrs, argv):
        self.mod_attrs, self.argv = mod_attrs, argv

    def __enter__(self):
        self.old = [(m, k, getattr(m, k)) for m, k, _ in self.mod_attrs]
        for m, k, v in self.mod_attrs: setattr(m, k, v)
        self.argv0 = sys.argv; sys.argv = ['x'] + self.argv
        return self

    def __exit__(self, *a):
        sys.argv = self.argv0
        for m, k, v in self.old: setattr(m, k, v)


def run_quiet(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn()
    return rc, buf.getvalue()


class DesktopEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(self.tmp.name)
        self.t = t
        (t / 'data' / 'cache' / 'repos').mkdir(parents=True)
        (t / 'hist').mkdir(); (t / 'out').mkdir()
        self.nodes = {'acme/regular': desktop_node(1, 'acme/regular', 'A regular desktop app', 300),
                      'acme/goodapp': desktop_node(2, 'acme/goodapp', 'A nice desktop app', 500),
                      'acme/badlib': desktop_node(3, 'acme/badlib', 'A library for things', 800)}
        for n, node in self.nodes.items():
            (t / 'data' / 'cache' / 'repos' / (n.replace('/', '__') + '.json')).write_text(
                json.dumps({'requested': n, 'fetched_at': time.time(), 'node': node}), encoding='utf-8')
        write_snaps_real(t / 'hist', {7: {'acme/regular': 290}})
        (t / 'data' / 'trending_candidates.txt').write_text('acme/goodapp\tgithub_trending:daily\nacme/badlib\tgithub_trending:weekly\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def run_build(self, extra, gh=None):
        t = self.t
        attrs = [(B, 'DATA', t / 'data'), (B, 'CACHE', t / 'data' / 'cache'), (B, 'REPOS_CACHE', t / 'data' / 'cache' / 'repos'),
                 (B, 'COST_LOG', t / 'data' / 'cache' / 'cost.jsonl'), (B, 'OUT', t / 'out'), (B, 'HIST', t / 'hist'),
                 (B, 'candidates', lambda: ['acme/regular'])]
        if gh is not None: attrs.append((TR, 'get_github_trending', gh))
        with Patched(attrs, ['--max-age-hours', '1000000'] + extra):
            return run_quiet(B.main)

    def test_default_run_has_trending_ready_and_never_calls_github(self):
        def boom(*a, **k): raise AssertionError('github.com/trending must not be touched by default')
        rc, _ = self.run_build([], gh=boom)
        self.assertEqual(rc, 0)
        doc = json.loads((self.t / 'out' / 'trending.json').read_text(encoding='utf-8'))
        self.assertTrue(doc['ready'])
        self.assertEqual(doc['items'], [{'slug': 'acme--regular', 'd7': 10, 'd30': None, 'rank': 1}])
        self.assertEqual(doc['github_trending']['enabled'], False)
        self.assertEqual(doc['sources_used'], ['stars_history'])
        cat = json.loads((self.t / 'out' / 'catalog.json').read_text(encoding='utf-8'))
        by = {c['slug']: c for c in cat['apps']}
        self.assertEqual(by['acme--regular']['trending'], {'d7': 10, 'd30': None, 'rank': 1})
        self.assertEqual(by['acme--goodapp']['trending'], {'d7': None, 'd30': None, 'rank': None})   # no history for it: null, not 0
        self.assertEqual(by['acme--goodapp']['sources'], ['github_trending'])
        detail = json.loads((self.t / 'out' / 'apps' / 'acme--regular.json').read_text(encoding='utf-8'))
        self.assertEqual(detail['trending']['rank'], 1)
        stats = json.loads((self.t / 'out' / 'stats.json').read_text(encoding='utf-8'))
        # candidates file (from an earlier opt-in run) is curated the same way: one passes (installer), one fails C4a
        self.assertEqual(stats['trending_candidates'], {'seen': 2, 'added': 1, 'already_known': 0, 'rejected': {'C4a': 1}})
        self.assertEqual(stats['trending'], {'ready': True, 'ranked': 1, 'badges': 1})
        self.assertNotIn('acme/badlib', by)
        self.assertTrue((self.t / 'hist' / ('snapshot-%s.json' % real_today().isoformat())).exists())

    def test_flag_with_failing_github_continues(self):
        (self.t / 'data' / 'trending_candidates.txt').unlink()
        fail = lambda cache=None, **k: {'enabled': True, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []}
        rc, out = self.run_build(['--with-github-trending'], gh=fail)
        self.assertEqual(rc, 0)
        doc = json.loads((self.t / 'out' / 'trending.json').read_text(encoding='utf-8'))
        self.assertEqual(doc['github_trending']['enabled'], True); self.assertEqual(doc['github_trending']['ok'], False)
        self.assertEqual(doc['sources_used'], ['stars_history'])
        self.assertTrue(doc['ready'])
        self.assertFalse((self.t / 'data' / 'trending_candidates.txt').exists())   # nothing fetched => nothing written

    def test_flag_with_working_github_writes_candidates_and_uses_them(self):
        (self.t / 'data' / 'trending_candidates.txt').unlink()
        ok = lambda cache=None, **k: {'enabled': True, 'ok': True, 'fetched_at': '2026-11-12T00:00:00Z', 'daily': ['acme/goodapp', 'acme/regular'], 'weekly': ['acme/badlib']}
        rc, _ = self.run_build(['--with-github-trending'], gh=ok)
        self.assertEqual(rc, 0)
        txt = (self.t / 'data' / 'trending_candidates.txt').read_text(encoding='utf-8')
        self.assertIn('acme/goodapp\tgithub_trending:daily', txt); self.assertIn('acme/badlib\tgithub_trending:weekly', txt)
        stats = json.loads((self.t / 'out' / 'stats.json').read_text(encoding='utf-8'))
        self.assertEqual(stats['trending_candidates'], {'seen': 3, 'added': 1, 'already_known': 1, 'rejected': {'C4a': 1}})
        doc = json.loads((self.t / 'out' / 'trending.json').read_text(encoding='utf-8'))
        self.assertEqual(doc['sources_used'], ['stars_history', 'github_trending'])
        self.assertEqual(doc['github_trending']['daily'], ['acme/goodapp', 'acme/regular'])

    def test_not_ready_without_history(self):
        for f in (self.t / 'hist').glob('*.json'): f.unlink()
        rc, _ = self.run_build([])
        self.assertEqual(rc, 0)
        doc = json.loads((self.t / 'out' / 'trending.json').read_text(encoding='utf-8'))
        self.assertFalse(doc['ready']); self.assertEqual(doc['items'], [])
        cat = json.loads((self.t / 'out' / 'catalog.json').read_text(encoding='utf-8'))
        for c in cat['apps']: self.assertEqual(c['trending'], {'d7': None, 'd30': None, 'rank': None})


def ai_rec(dbid, nwo, stars, fork=False, pkg=None):
    name = nwo.split('/')[1]
    texts = {}
    if pkg:
        texts['package.json'] = json.dumps({'name': pkg, 'version': '1.0.0'})
        texts['server.json'] = json.dumps({'name': 'io.github.%s' % nwo.replace('/', '/'), 'description': 'd', 'repository': {'url': 'https://github.com/' + nwo},
                                           'packages': [{'registryType': 'npm', 'identifier': pkg, 'transport': {'type': 'stdio'}}]})
    node = {'databaseId': dbid, 'nameWithOwner': nwo, 'description': 'An MCP server ' + name, 'stargazerCount': stars, 'forkCount': 0,
            'isFork': fork, 'isArchived': False, 'isDisabled': False,
            'owner': {'login': nwo.split('/')[0], 'avatarUrl': 'https://a', 'createdAt': '2020-01-01T00:00:00Z'},
            'licenseInfo': {'spdxId': 'MIT'}, 'homepageUrl': None, 'pushedAt': fresh_iso(5), 'latestRelease': None, 'topics': []}
    return {'node': node, 'texts': texts, 'readme': '', 'trees': {}, 'truncated_manifests': []}


class AiEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.t = pathlib.Path(self.tmp.name)
        c = t / 'data' / 'cache_ai'
        (c / 'repos').mkdir(parents=True); (t / 'hist').mkdir(); (t / 'out').mkdir()
        (c / 'registry.json').write_text(json.dumps({'complete': True, 'fetched_at': time.time(), 'records_seen': 1, 'pages': 1, 'skipped_status': {},
            'servers': [{'name': 'io.github.acme/main', 'description': 'd', 'repository': {'url': 'https://github.com/acme/main-mcp'},
                         'packages': [{'registryType': 'npm', 'identifier': 'main-mcp', 'transport': {'type': 'stdio'}}]}]}), encoding='utf-8')
        stars = {'acme/main-mcp': {'id': 1, 'stars': 900, 'name': 'acme/main-mcp'}, 'acme/good-mcp': {'id': 2, 'stars': 400, 'name': 'acme/good-mcp'},
                 'acme/bad-mcp': {'id': 3, 'stars': 700, 'name': 'acme/bad-mcp'}}
        (c / 'stars.json').write_text(json.dumps({'fetched_at': time.time(), 'repos': stars}), encoding='utf-8')
        for rec in (ai_rec(1, 'acme/main-mcp', 900, pkg='main-mcp'), ai_rec(2, 'acme/good-mcp', 400, pkg='good-mcp'),
                    ai_rec(3, 'acme/bad-mcp', 700, fork=True, pkg='bad-mcp')):
            (c / 'repos' / (rec['node']['nameWithOwner'].lower().replace('/', '--') + '.json')).write_text(
                json.dumps({'fetched_at': time.time(), 'rec': rec}), encoding='utf-8')
        write_snaps_real(t / 'hist', {7: {'acme/main-mcp': 880}}, prefix='ai-')
        (t / 'data' / 'trending_candidates.txt').write_text('acme/good-mcp\tgithub_trending:daily\nacme/bad-mcp\tgithub_trending:weekly\n', encoding='utf-8')
        self.c = c

    def tearDown(self):
        self.tmp.cleanup()

    def run_build(self, extra, gh=None):
        t, c = self.t, self.c
        attrs = [(BA, 'DATA', t / 'data'), (BA, 'CACHE', c), (BA, 'COST_LOG', c / 'cost.jsonl'), (BA, 'OUT', t / 'out'), (BA, 'HIST', t / 'hist'),
                 (B, 'CACHE', t / 'data' / 'cache_b'), (B, 'load_token', lambda: None)]
        if gh is not None: attrs.append((TR, 'get_github_trending', gh))
        with Patched(attrs, ['--offline'] + extra):
            return run_quiet(BA.main)

    def test_default_run(self):
        def boom(*a, **k): raise AssertionError('github.com/trending must not be touched by default')
        rc, _ = self.run_build([], gh=boom)
        self.assertEqual(rc, 0)
        doc = json.loads((self.t / 'out' / 'trending-ai.json').read_text(encoding='utf-8'))
        self.assertTrue(doc['ready'])
        self.assertEqual(doc['items'], [{'slug': 'acme--main-mcp', 'd7': 20, 'd30': None, 'rank': 1}])
        self.assertFalse(doc['github_trending']['enabled'])
        cat = json.loads((self.t / 'out' / 'catalog-ai.json').read_text(encoding='utf-8'))
        by = {e['slug']: e for e in cat['entries']}
        self.assertEqual(by['acme--main-mcp']['trending'], {'ready': True, 'd7': 20, 'd30': None, 'rank': 1})
        self.assertEqual(by['acme--good-mcp']['trending'], {'ready': True, 'd7': None, 'd30': None, 'rank': None})
        self.assertIn({'kind': 'github_trending', 'ref': 'daily'}, by['acme--good-mcp']['sources'])
        self.assertNotIn('acme--bad-mcp', by)
        detail = json.loads((self.t / 'out' / 'ai' / 'acme--main-mcp.json').read_text(encoding='utf-8'))
        self.assertEqual(detail['trending']['rank'], 1)
        stats = json.loads((self.t / 'out' / 'stats-ai.json').read_text(encoding='utf-8'))
        self.assertEqual(stats['trending_candidates'], {'seen': 2, 'added': 1, 'already_known': 0, 'rejected': {'owner_unclear': 1}})
        self.assertEqual(stats['sources']['entries_per_source']['github_trending'], 1)
        self.assertEqual(stats['trending'], {'ready': True, 'ranked': 1, 'badges': 1})

    def test_flag_failing_github_continues(self):
        fail = lambda cache=None, **k: {'enabled': True, 'ok': False, 'fetched_at': None, 'daily': [], 'weekly': []}
        rc, _ = self.run_build(['--with-github-trending'], gh=fail)
        self.assertEqual(rc, 0)
        doc = json.loads((self.t / 'out' / 'trending-ai.json').read_text(encoding='utf-8'))
        self.assertEqual((doc['github_trending']['enabled'], doc['github_trending']['ok']), (True, False))
        self.assertEqual(doc['sources_used'], ['stars_history'])

    def test_offline_flag_does_not_fetch(self):
        def boom(*a, **k): raise AssertionError('no fetch in offline mode')
        rc, _ = self.run_build(['--with-github-trending'], gh=boom)
        self.assertEqual(rc, 0)

    def test_not_ready_without_history(self):
        for f in (self.t / 'hist').glob('*.json'): f.unlink()
        self.run_build([])
        doc = json.loads((self.t / 'out' / 'trending-ai.json').read_text(encoding='utf-8'))
        self.assertFalse(doc['ready']); self.assertEqual(doc['items'], [])
        cat = json.loads((self.t / 'out' / 'catalog-ai.json').read_text(encoding='utf-8'))
        for e in cat['entries']: self.assertEqual(e['trending'], {'ready': False, 'd7': None, 'd30': None, 'rank': None})


class CliDefaults(unittest.TestCase):
    def test_flag_default_off_in_both_builders(self):
        for f in ('build_catalog.py', 'build_ai.py'):
            src = (HERE / f).read_text(encoding='utf-8')
            self.assertIn("'--with-github-trending', action='store_true'", src)
            self.assertIn("'--history-dir'", src)


if __name__ == '__main__':
    unittest.main(verbosity=1)
