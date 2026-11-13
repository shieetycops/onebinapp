import { test, expect, type Browser, type Page } from '@playwright/test';

// "Top 10 today": the ten biggest one-day star gainers per section. The fixture build has no daily block (so it must be
// hidden); the data is injected in flight (page.route) so one build covers every state.
const GH_OFF = { enabled: false, ok: false, fetched_at: null, daily: [], weekly: [] };
const base = { generated_at: '2026-11-12T00:00:00Z', window_days: { d7: 7, d30: 30 }, items: [], badges: 0, sources_used: ['stars_history'], snapshot_dates: ['2026-11-11', '2026-11-12'], github_trending: GH_OFF };

type Item = { slug: string; d1: number };
const daily = (items: Item[], ready = true) => ({ ...base, ready: false, daily: { ready, baseline: '2026-11-11', items } });

async function open(browser: Browser, url: string, file: 'trending' | 'trending-ai', body: unknown, vp?: { width: number; height: number }): Promise<Page> {
  const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', viewport: vp });
  const page = await ctx.newPage();
  await page.route(`**/data/${file}.json`, (r) => r.fulfill({ json: body }));
  await page.goto(url);
  return page;
}

test.describe('top 10 today: desktop apps', () => {
  test('hidden when the build has no daily data (fixture default)', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('app-card').first()).toBeVisible();
    await expect(page.getByTestId('top-daily')).toHaveCount(0);
  });

  test('hidden when daily.ready is false, even with items', async ({ browser }) => {
    const page = await open(browser, '/', 'trending', daily([{ slug: 'acme--winpad', d1: 5 }], false));
    await expect(page.getByTestId('app-card').first()).toBeVisible();
    await expect(page.getByTestId('top-daily')).toHaveCount(0);
    await page.context().close();
  });

  test('shows the items in the given order with their gain, links to the app page', async ({ browser }) => {
    const page = await open(browser, '/', 'trending', daily([
      { slug: 'acme--macsplit', d1: 42 }, { slug: 'acme--winpad', d1: 17 }, { slug: 'acme--linuxonly', d1: 3 },
    ]));
    const rows = page.getByTestId('top-row');
    await expect(rows).toHaveCount(3);
    expect(await rows.evaluateAll((els) => els.map((e) => e.getAttribute('data-slug')))).toEqual(['acme--macsplit', 'acme--winpad', 'acme--linuxonly']);
    await expect(page.getByTestId('top-gain')).toHaveText(['+42bintang', '+17bintang', '+3bintang']);
    await expect(rows.first()).toHaveAttribute('href', '/app/acme--macsplit/');
    await expect(page.getByTestId('top-daily')).toContainText('11 November 2026');
    await rows.first().click();
    await expect(page).toHaveURL(/\/app\/acme--macsplit\/$/);
    await page.context().close();
  });

  test('never more than 10 rows; unknown slugs and developer tools are skipped', async ({ browser }) => {
    const cat = JSON.parse((await import('node:fs')).readFileSync('tests/fixtures/data/catalog.json', 'utf8'));
    const dev = cat.apps.find((a: { dev: boolean }) => a.dev).slug as string;
    const normal = cat.apps.filter((a: { dev: boolean }) => !a.dev).map((a: { slug: string }) => a.slug) as string[];
    const items = [{ slug: 'ghost--missing', d1: 99 }, { slug: dev, d1: 98 }, ...normal.slice(0, 14).map((s, i) => ({ slug: s, d1: 50 - i }))];
    const page = await open(browser, '/', 'trending', daily(items));
    await expect(page.getByTestId('top-row')).toHaveCount(10);
    const got = await page.getByTestId('top-row').evaluateAll((els) => els.map((e) => e.getAttribute('data-slug')));
    expect(got).toEqual(normal.slice(0, 10));
    await page.context().close();
  });

  test('is its own section: AI home does not show desktop daily data', async ({ browser }) => {
    const page = await open(browser, '/ai/', 'trending', daily([{ slug: 'acme--winpad', d1: 5 }]));
    await expect(page.getByTestId('ai-card').first()).toBeVisible();
    await expect(page.getByTestId('top-daily')).toHaveCount(0);
    await page.context().close();
  });

  test('English text and the heading', async ({ browser }) => {
    const page = await open(browser, '/', 'trending', daily([{ slug: 'acme--winpad', d1: 5 }]));
    await page.getByTestId('lang-en').click();
    await expect(page.getByRole('heading', { name: /Most popular today/ })).toBeVisible();
    await expect(page.getByTestId('top-daily')).toContainText('Compared with the 11 November 2026 snapshot');
    await page.context().close();
  });
});

test.describe('top 10 today: AI tools', () => {
  test('shows AI entries from trending-ai.json, links to the AI page', async ({ browser }) => {
    const page = await open(browser, '/ai/', 'trending-ai', daily([{ slug: 'acme--zeta-all', d1: 21 }, { slug: 'acme--alpha-mcp', d1: 8 }]));
    const rows = page.getByTestId('top-row');
    await expect(rows).toHaveCount(2);
    expect(await rows.evaluateAll((els) => els.map((e) => e.getAttribute('data-slug')))).toEqual(['acme--zeta-all', 'acme--alpha-mcp']);
    await expect(rows.first()).toHaveAttribute('href', '/ai/acme--zeta-all/');
    await page.context().close();
  });

  test('hidden without daily data', async ({ page }) => {
    await page.goto('/ai/');
    await expect(page.getByTestId('ai-card').first()).toBeVisible();
    await expect(page.getByTestId('top-daily')).toHaveCount(0);
  });
});

test.describe('top 10 today: phone 360x740', () => {
  test('rows fit without horizontal scroll', async ({ browser }) => {
    const page = await open(browser, '/', 'trending', daily([{ slug: 'acme--macsplit', d1: 4200 }, { slug: 'acme--androidonly', d1: 17 }]), { width: 360, height: 740 });
    await expect(page.getByTestId('top-row').first()).toBeVisible();
    const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
    expect(m.sw).toBeLessThanOrEqual(m.iw);
    await page.context().close();
  });
});

test.describe('brand and about page', () => {
  test('the site is called onebin', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle('onebin');
    await expect(page.locator('header .wordmark')).toContainText('onebin');
    await expect(page.locator('footer .wordmark')).toContainText('onebin');
    expect(await page.locator('body').innerText()).not.toContain('Jembatan');
    await page.goto('/tentang/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Tentang onebin');
  });

  test('about page keeps its numbered cards and fits a phone', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', viewport: { width: 360, height: 740 } });
    const page = await ctx.newPage();
    await page.goto('/tentang/');
    await expect(page.locator('.about-card').first()).toBeVisible();
    expect(await page.locator('.about-card').count()).toBeGreaterThanOrEqual(6);
    const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
    expect(m.sw).toBeLessThanOrEqual(m.iw);
    await ctx.close();
  });
});
