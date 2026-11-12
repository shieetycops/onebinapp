"""End-to-end checks of the daily desktop build on the REAL cached data, with all outputs redirected to a temp dir
(site/public/data, data/history and data/changelog are not touched).  Slow (about a minute per scenario); skipped when no cache exists.
Run: python -I scripts/catalog/test_daily_e2e.py"""
import sys, json, pathlib, tempfile, unittest, io, contextlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import build_catalog as B       # noqa: E402
import pipeline as PL           # noqa: E402


@unittest.skipUnless((B.REPOS_CACHE).exists() and any(B.REPOS_CACHE.glob('*.json')), 'no cache')
class DailyE2E(unittest.TestCase):
    def run_main(self, tmp, mutate_freshness=None, extra=()):
        saved = (B.OUT, B.HIST, B.CHANGELOG, B.Fetcher.fetch, B.load_token, PL.classify_freshness, sys.argv)
        B.OUT, B.HIST, B.CHANGELOG = tmp / 'out', tmp / 'hist', tmp / 'changelog'
        B.HIST.mkdir(parents=True, exist_ok=True)
        B.Fetcher.fetch = lambda self, names, batch: list(names)          # every fetch fails: the old cache must be used
        B.load_token = lambda: 'x'
        real = PL.classify_freshness
        def patched(names, fa, now, mah, msd):
            fr = real(names, fa, now, 10 ** 9, msd)                       # everything fresh by age ...
            return mutate_freshness(fr) if mutate_freshness else fr       # ... then the scenario decides
        PL.classify_freshness = patched
        sys.argv = ['build_catalog.py', '--max-age-hours', '0.0001'] + list(extra)    # tiny max-age: every repo is "pending", every fetch fails
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                rc = B.main()
        finally:
            B.OUT, B.HIST, B.CHANGELOG, B.Fetcher.fetch, B.load_token, PL.classify_freshness, sys.argv = saved
        return rc, buf.getvalue()

    def test_guard_blocks_everything_when_most_repos_are_stale(self):
        def all_stale(fr):
            return {'fresh': [], 'stale': [(n, 1.0) for n in fr['fresh']], 'expired': fr['expired'], 'missing': fr['missing']}
        tmp = pathlib.Path(tempfile.mkdtemp())
        rc, out = self.run_main(tmp, all_stale)
        self.assertEqual(rc, 4); self.assertIn('GUARD', out)
        self.assertFalse((tmp / 'out' / 'catalog.json').exists())           # nothing written
        self.assertFalse(list((tmp / 'hist').glob('*.json'))); self.assertFalse((tmp / 'changelog').exists())

    def test_a_few_failed_repos_use_old_data_and_the_build_continues(self):
        picked = {}
        def some_stale_some_expired(fr):
            fresh = list(fr['fresh'])
            picked['stale'], picked['expired'] = fresh[:60], fresh[60:63]
            return {'fresh': fresh[63:], 'stale': [(n, 2.0) for n in picked['stale']], 'expired': [(n, 9.0) for n in picked['expired']], 'missing': []}
        tmp = pathlib.Path(tempfile.mkdtemp())
        rc, out = self.run_main(tmp, some_stale_some_expired)
        self.assertEqual(rc, 0, out[-500:])
        stats = json.loads((tmp / 'out' / 'stats.json').read_text(encoding='utf-8'))
        f = stats['freshness']
        self.assertEqual((f['stale_reused'], f['stale_expired']), (60, 3))
        self.assertEqual(stats['dropped']['stale_expired'], 3)
        cat = json.loads((tmp / 'out' / 'catalog.json').read_text(encoding='utf-8'))
        have = {a['repo'].lower() for a in cat['apps']}
        # an expired repo is not published; a stale one still is when it passed curation before
        self.assertFalse(have & {n.lower() for n in picked['expired']})
        self.assertGreater(len(have), 1000)
        meta = json.loads((tmp / 'out' / 'meta.json').read_text(encoding='utf-8'))
        self.assertEqual(meta['desktop'], cat['generated_at'])              # the footer date is the build time
        rows = [json.loads(l) for l in (tmp / 'changelog' / 'desktop.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertTrue(rows[-1]['baseline']); self.assertEqual(rows[-1]['stale_reused'], 60)


if __name__ == '__main__':
    unittest.main()
