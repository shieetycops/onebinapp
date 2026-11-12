import { test, expect, type Browser, type Page } from '@playwright/test';

// Trending (SPEC_TRENDING.md). The fixture build has ready=false for both sections; ready=true is produced by rewriting the
// fixture JSON in flight (page.route), so one build covers both states. Desktop and AI data are separate files.
const BAD_WORD = /(?<![\w-])(aman|safe)(?![\w-])/i;
const GH_OFF = { enabled: false, ok: false, fetched_at: null, daily: [], weekly: [] };

type Opts = { app?: boolean; ai?: boolean; github?: { enabled: boolean; ok: boolean }; viewport?: { width: number; height: number } };

function doc(ready: boolean, gh?: { enabled: boolean; ok: boolean }) {
  const g = gh ? { ...GH_OFF, ...gh, fetched_at: gh.ok ? '2026-11-12T00:00:00Z' : null } : GH_OFF;
  const used = ['stars_history'].concat(gh && gh.enabled && gh.ok ? ['github_trending'] : []);
  return { ready, generated_at: '2026-11-12T00:00:00Z', window_days: { d7: 7, d30: 30 }, items: [], badges: 0, sources_used: used, snapshot_dates: ['2026-11-01'], github_trending: g };
}

const DESK: Record<string, { d7: number; d30: number | null; rank: number }> = {
  'acme--macsplit': { d7: 40, d30: 90, rank: 1 },      // 3000 stars -> threshold 30 -> badge
  'acme--winpad': { d7: 12, d30: null, rank: 2 },      // 5000 stars -> threshold 50 -> ranked but NO badge
  'acme--linuxonly': { d7: 30, d30: 31, rank: 3 },     // 2700 stars -> threshold 27 -> badge
};
const AI: Record<string, { d7: number; d30: number | null; rank: number }> = {
  'acme--zeta-all': { d7: 30, d30: 31, rank: 1 },      // 1500 stars -> threshold 15 -> badge
  'acme--beta-skill': { d7: 20, d30: null, rank: 2 },  // 7000 stars -> threshold 70 -> ranked, no badge
  'acme--alpha-mcp': { d7: 100, d30: 120, rank: 3 },   // 9000 stars -> threshold 90 -> badge
};

async function mocked(browser: Browser, o: Opts = {}): Promise<Page> {
  const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', viewport: o.viewport });
  const page = await ctx.newPage();
  await page.route('**/data/trending.json', (r) => r.fulfill({ json: doc(!!o.app, o.github) }));
  await page.route('**/data/trending-ai.json', (r) => r.fulfill({ json: doc(!!o.ai, o.github) }));
  if (o.app) {
    await page.route('**/data/catalog.json', async (route) => {
      const res = await route.fetch();
      const j = await res.json();
      for (const a of j.apps) if (DESK[a.slug]) a.trending = DESK[a.slug];
      await route.fulfill({ response: res, json: j });
    });
  }
  if (o.ai) {
    await page.route('**/data/catalog-ai.json', async (route) => {
      const res = await route.fetch();
      const j = await res.json();
      for (const e of j.entries) if (AI[e.slug]) e.trending = { ready: true, ...AI[e.slug] };
      await route.fulfill({ response: res, json: j });
    });
  }
  return page;
}

const slugs = async (page: Page, id: string) => page.getByTestId(id).evaluateAll((els) => els.map((e) => e.getAttribute('data-slug')));

test.describe('trending: desktop home', () => {
  test('ready=true: tab appears, ranked list in rank order, badge only on cards that pass the threshold', async ({ browser }) => {
    const page = await mocked(browser, { app: true });
    await page.goto('/');
    const tab = page.getByTestId('sort-trending');
    await expect(tab).toBeVisible();
    await expect(tab).toHaveText('Sedang naik');
    await tab.click();
    await expect(tab).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('app-card')).toHaveCount(3);
    expect(await slugs(page, 'app-card')).toEqual(['acme--macsplit', 'acme--winpad', 'acme--linuxonly']);
    for (const [slug, has] of [['acme--macsplit', 1], ['acme--winpad', 0], ['acme--linuxonly', 1]] as const) {
      await expect(page.locator(`[data-testid="app-card"][data-slug="${slug}"]`).getByTestId('rising-badge')).toHaveCount(has);
    }
    await expect(page.getByTestId('rising-badge').first()).toHaveText('naik daun');
    await page.context().close();
  });

  test('badges also show in the other sorts; unranked cards never get one', async ({ browser }) => {
    const page = await mocked(browser, { app: true });
    await page.goto('/');
    await page.getByTestId('sort-popular').click();
    await expect(page.getByTestId('rising-badge')).toHaveCount(2);
    await expect(page.locator('[data-testid="app-card"][data-slug="acme--silentapp"]').getByTestId('rising-badge')).toHaveCount(0);
    await page.context().close();
  });

  test('desktop ready does not switch on the AI section (separate data)', async ({ browser }) => {
    const page = await mocked(browser, { app: true, ai: false });
    await page.goto('/ai/');
    await expect(page.getByTestId('aisort-stars')).toBeVisible();
    await expect(page.getByTestId('aisort-trending')).toHaveCount(0);
    await expect(page.getByTestId('rising-badge')).toHaveCount(0);
    await page.context().close();
  });

  test('ready=false: no tab, no badge, nothing about trending on the cards', async ({ browser }) => {
    const page = await mocked(browser, { app: false, ai: false });
    await page.goto('/');
    await expect(page.getByTestId('app-card').first()).toBeVisible();
    await expect(page.getByTestId('sort-trending')).toHaveCount(0);
    await expect(page.getByTestId('rising-badge')).toHaveCount(0);
    await page.context().close();
  });
});

test.describe('trending: AI home', () => {
  test('ready=true: tab, rank order, badges; desktop home stays without a tab', async ({ browser }) => {
    const page = await mocked(browser, { ai: true });
    await page.goto('/ai/');
    const tab = page.getByTestId('aisort-trending');
    await expect(tab).toBeVisible();
    await tab.click();
    await expect(page.getByTestId('ai-card')).toHaveCount(3);
    expect(await slugs(page, 'ai-card')).toEqual(['acme--zeta-all', 'acme--beta-skill', 'acme--alpha-mcp']);
    for (const [slug, has] of [['acme--zeta-all', 1], ['acme--beta-skill', 0], ['acme--alpha-mcp', 1]] as const) {
      await expect(page.locator(`[data-testid="ai-card"][data-slug="${slug}"]`).getByTestId('rising-badge')).toHaveCount(has);
    }
    await page.goto('/');
    await expect(page.getByTestId('app-card').first()).toBeVisible();
    await expect(page.getByTestId('sort-trending')).toHaveCount(0);
    await expect(page.getByTestId('rising-badge')).toHaveCount(0);
    await page.context().close();
  });

  test('ready=false in trending-ai.json: no tab', async ({ browser }) => {
    const page = await mocked(browser, { ai: false });
    await page.goto('/ai/');
    await expect(page.getByTestId('ai-card').first()).toBeVisible();
    await expect(page.getByTestId('aisort-trending')).toHaveCount(0);
    await page.context().close();
  });
});

test.describe('trending: phone viewport 360x740', () => {
  const vp = { width: 360, height: 740 };
  for (const [name, o, url, tabId, cardId] of [
    ['desktop', { app: true }, '/', 'sort-trending', 'app-card'],
    ['ai', { ai: true }, '/ai/', 'aisort-trending', 'ai-card'],
  ] as const) {
    test(`${name}: tab and badges fit without horizontal scroll`, async ({ browser }) => {
      const page = await mocked(browser, { ...o, viewport: vp });
      await page.goto(url);
      await expect(page.getByTestId(tabId)).toBeVisible();
      await page.getByTestId(tabId).click();
      await expect(page.getByTestId(cardId)).toHaveCount(3);
      await expect(page.getByTestId('rising-badge').first()).toBeVisible();
      const w = await page.evaluate(() => document.documentElement.scrollWidth);
      expect(w).toBeLessThanOrEqual(360);
      const box = await page.getByTestId(tabId).boundingBox();
      expect(box!.x + box!.width).toBeLessThanOrEqual(360);
      await page.context().close();
    });
  }
});

test.describe('trending: language', () => {
  test('id/en labels for tab, badge and fallback', async ({ browser }) => {
    const page = await mocked(browser, { app: true });
    await page.goto('/');
    await page.getByTestId('lang-en').click();
    await expect(page.getByTestId('sort-trending')).toHaveText('Trending');
    await page.getByTestId('sort-trending').click();
    await expect(page.getByTestId('rising-badge').first()).toHaveText('rising');
    await page.getByTestId('lang-id').click();
    await expect(page.getByTestId('sort-trending')).toHaveText('Sedang naik');
    await expect(page.getByTestId('rising-badge').first()).toHaveText('naik daun');
    await page.context().close();
  });

  test('AI id/en', async ({ browser }) => {
    const page = await mocked(browser, { ai: true });
    await page.goto('/ai/');
    await page.getByTestId('lang-en').click();
    await expect(page.getByTestId('aisort-trending')).toHaveText('Trending');
    await page.getByTestId('aisort-trending').click();
    await expect(page.getByTestId('rising-badge').first()).toHaveText('rising');
    await page.context().close();
  });
});

test.describe('trending: /tentang', () => {
  test('not ready: says so, lists our star history only, GitHub trending off, Trendshift and downloads explained', async ({ browser }) => {
    const page = await mocked(browser, {});
    await page.goto('/tentang/');
    const box = page.getByTestId('about-trending');
    await expect(box).toBeVisible();
    for (const id of ['app', 'ai']) {
      const b = page.getByTestId(`trend-${id}`);
      await expect(b).toHaveAttribute('data-ready', 'false');
      await expect(b).toContainText('Belum ada tren');
      await expect(b.getByTestId('trend-src-history')).toHaveCount(1);
      await expect(b.getByTestId('trend-src-github')).toHaveCount(0);
      await expect(b.getByTestId('trend-github-off')).toHaveCount(1);
    }
    await expect(box).toContainText('Trendshift tidak dipakai');
    await expect(box).toContainText('berbayar');
    await expect(box).toContainText('Jumlah unduhan tidak dipakai untuk tren');
    await expect(box).toContainText('maksimal 15');
    expect(await box.innerText()).not.toMatch(BAD_WORD);
    await page.context().close();
  });

  test('ready with github trending enabled and ok: both sources listed', async ({ browser }) => {
    const page = await mocked(browser, { app: true, ai: true, github: { enabled: true, ok: true } });
    await page.goto('/tentang/');
    for (const id of ['app', 'ai']) {
      const b = page.getByTestId(`trend-${id}`);
      await expect(b).toHaveAttribute('data-ready', 'true');
      await expect(b.getByTestId('trend-src-history')).toHaveCount(1);
      await expect(b.getByTestId('trend-src-github')).toContainText('github.com/trending');
      await expect(b.getByTestId('trend-github-off')).toHaveCount(0);
    }
    await page.context().close();
  });

  test('github trending enabled but failed: not listed as a source', async ({ browser }) => {
    const page = await mocked(browser, { app: true, github: { enabled: true, ok: false } });
    await page.goto('/tentang/');
    const b = page.getByTestId('trend-app');
    await expect(b.getByTestId('trend-src-github')).toHaveCount(0);
    await expect(b.getByTestId('trend-github-off')).toHaveCount(1);
    await page.context().close();
  });

  test('English text', async ({ browser }) => {
    const page = await mocked(browser, {});
    await page.goto('/tentang/');
    await page.getByTestId('lang-en').click();
    const box = page.getByTestId('about-trending');
    await expect(box).toContainText('Trending data sources');
    await expect(box).toContainText('No trending yet');
    await expect(box).toContainText('Trendshift is not used');
    await expect(box).toContainText('Download counts are not used for trending');
    expect(await box.innerText()).not.toMatch(BAD_WORD);
    await page.context().close();
  });
});
