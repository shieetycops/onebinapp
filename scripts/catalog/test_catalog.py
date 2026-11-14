"""Run: python -I scripts/catalog/test_catalog.py   (stdlib unittest; no network)"""
import sys, json, pathlib, unittest, tempfile, os, re
HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import curation as CUR, categories as CAT, build_catalog as B
DATA = B.DATA


HAVE_RAW = (DATA / 'round3' / 'raw').is_dir() and any((DATA / 'round3' / 'raw').glob('*.meta.json'))
NEED_RAW = unittest.skipUnless(HAVE_RAW, 'data/round3/raw is gitignored; these run only where it exists locally')


class Curation(unittest.TestCase):
    @NEED_RAW
    def test_round3_gate_300(self):
        dec = json.loads((DATA / 'round3' / 'curation_decisions.json').read_text(encoding='utf-8'))
        self.assertEqual(len(dec), 300)
        for name, v in dec.items():
            ok, why = CUR.curate_rest_file(DATA / 'round3' / 'raw' / (name.replace('/', '__') + '.meta.json'))
            self.assertEqual(ok, v['curated'], name)
            if not ok and not v['why'][0].startswith('meta_http'):
                self.assertEqual(why, v['why'], name)

    @NEED_RAW
    def test_graphql_adapter_matches_rest_on_round3(self):
        n = 0
        for p in sorted((DATA / 'round3' / 'raw').glob('*.meta.json'))[:200]:
            m = json.loads(p.read_bytes())
            if 'full_name' not in m: continue
            node = {'nameWithOwner': m['full_name'], 'description': m['description'], 'isFork': m['fork'], 'isArchived': m['archived'],
                    'isDisabled': m['disabled'], 'stargazerCount': m['stargazers_count'],
                    'repositoryTopics': {'nodes': [{'topic': {'name': t}} for t in m.get('topics') or []]}}
            self.assertEqual(CUR.curate(CUR.meta_from_graphql(node)), CUR.curate(m), m['full_name']); n += 1
        self.assertGreater(n, 100)

    def test_deny_lists_loaded(self):
        d = CUR.load_denied(DATA)
        self.assertIn('microsoft/playwright', d); self.assertIn('pyqtgraph/pyqtgraph', d)


class Hashes(unittest.TestCase):
    def test_sha_matches(self):
        self.assertEqual(B.PICKER_SHA, B.sha256_file(B.ROOT / 'scripts' / 'picker_v3.py'))


class Categories(unittest.TestCase):
    def test_priority_and_fallback(self):
        self.assertEqual(CAT.categorize(['music-player', 'cli']), ('media', True))
        self.assertEqual(CAT.categorize(['electron', 'desktop-app']), ('alat', False))
        self.assertEqual(CAT.categorize([]), ('alat', False))
        self.assertEqual(CAT.categorize(['git-client']), ('developer', True))
        self.assertEqual(CAT.categorize(['file-manager']), ('alat', True))
        for c in CAT.CATEGORY_IDS: self.assertIn(c, CAT.TOPICS)


class Builder(unittest.TestCase):
    def test_apk_rule(self):
        self.assertEqual(B.pick_android(['app-universal.apk', 'app-arm64-v8a.apk']), 'app-universal.apk')
        self.assertIsNone(B.pick_android(['a-arm64-v8a.apk', 'a-x86_64.apk']))
        self.assertEqual(B.pick_android(['x.apk']), 'x.apk')
        self.assertIsNone(B.pick_android(['readme.txt']))

    def test_release_and_platforms(self):
        rel = {'tagName': 'v1', 'name': 'v1', 'isPrerelease': False, 'isDraft': False, 'publishedAt': '2026-01-01T00:00:00Z', 'description': 'x' * 5000,
               'url': 'u', 'releaseAssets': {'nodes': [{'name': 'App-1.0-setup-x64.exe', 'size': 1, 'downloadCount': 3, 'downloadUrl': 'd1', 'updatedAt': ''},
                                                        {'name': 'App.dmg', 'size': 1, 'downloadCount': 0, 'downloadUrl': 'd2', 'updatedAt': ''},
                                                        {'name': 'App.exe.sha256', 'size': 1, 'downloadCount': 0, 'downloadUrl': 'd3', 'updatedAt': ''}]}}
        r = B.release_info(rel)
        self.assertEqual(len(r['notes_md']), 4000)
        self.assertEqual(B.release_platforms(r), {'windows', 'macos'})
        self.assertEqual(r['picks']['windows-x64'], 'App-1.0-setup-x64.exe')
        self.assertIsNone(r['picks']['linux-x64'])
        self.assertEqual([a['kind'] for a in r['assets']], ['exe', 'dmg', 'checksum'])

    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / 'a' / 'b.json'
            B.atomic_write(p, '{"x":1}')
            self.assertEqual(p.read_text(encoding='utf-8'), '{"x":1}')
            self.assertEqual([f.name for f in p.parent.iterdir()], ['b.json'])

    def test_builder_text_has_no_forbidden_word(self):
        self.assertNotRegex(json.dumps(B.TRUST_PICKER), r'(?i)\baman\b')
        for f in HERE.glob('*.py'):
            if f.name == 'test_catalog.py': continue
            self.assertNotRegex(f.read_text(encoding='utf-8'), r'(?i)\baman\b', f.name)


class Outputs(unittest.TestCase):
    def test_no_token_in_outputs(self):
        tok = B.load_token()
        if not tok: self.skipTest('no token')
        hits = 0
        for root in (B.OUT, B.CACHE, B.ROOT / 'data' / 'catalog_test_out', B.HIST, HERE.parent.parent / 'docs'):
            if not root.exists(): continue
            for p in root.rglob('*'):
                if p.is_file() and tok in p.read_text(encoding='utf-8', errors='replace'): hits += 1
        self.assertEqual(hits, 0)

    def test_catalog_shape_if_built(self):
        p = B.OUT / 'catalog.json'
        if not p.exists(): self.skipTest('no full build yet')
        c = json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(c['count'], len(c['apps']))
        keys = {'slug', 'repo', 'name', 'owner', 'avatar', 'desc', 'stars', 'platforms', 'category', 'dev', 'latest_release_at', 'is_new', 'version', 'trust', 'trending'}
        for a in c['apps']:
            self.assertTrue(keys <= set(a)); self.assertLessEqual(len(a['desc']), 160)
            self.assertIn(a['category'], CAT.CATEGORY_IDS); self.assertEqual(a['slug'], a['slug'].lower())
            self.assertTrue((B.OUT / 'apps' / (a['slug'] + '.json')).exists())


if __name__ == '__main__':
    unittest.main(verbosity=1)
