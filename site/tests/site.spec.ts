import { test, expect, type Browser, type Page } from '@playwright/test';

const UAS = {
  windows: { ua: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36', platform: 'Windows' },
  macos: { ua: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36', platform: 'macOS' },
  linux: { ua: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36', platform: 'Linux' },
  android: { ua: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36', platform: 'Android' },
} as const;
type K = keyof typeof UAS;

// Finding (see test 1): Playwright's userAgent override also changes navigator.userAgentData.platform in this
// Chromium, so no addInitScript stub is needed. Test 1 fails loudly if that ever stops being true.
async function pageAs(browser: Browser, os: K, opts: { viewport?: { width: number; height: number } } = {}): Promise<Page> {
  const ctx = await browser.newContext({ userAgent: UAS[os].ua, baseURL: 'http://localhost:4173', ...opts });
  return ctx.newPage();
}

test.describe('user agent override', () => {
  for (const os of Object.keys(UAS) as K[]) {
    test(`1. userAgent override also changes navigator.userAgentData (${os})`, async ({ browser }) => {
      const page = await pageAs(browser, os);
      await page.goto('/');
      const r = await page.evaluate(() => {
        const u = (navigator as unknown as { userAgentData?: { platform: string } }).userAgentData;
        return { ua: navigator.userAgent, platform: u ? u.platform : null };
      });
      console.log(`UA-FINDING ${os}: ${JSON.stringify(r)}`);
      expect(r.ua).toBe(UAS[os].ua);
      expect(r.platform).toBe(UAS[os].platform);
      await page.context().close();
    });
  }
});

test.describe('app page: download button', () => {
  test('exact pick on Windows links to the real asset URL', async ({ browser }) => {
    const page = await pageAs(browser, 'windows');
    await page.goto('/app/acme--winpad/');
    const btn = page.getByTestId('dl-btn');
    await expect(btn).toHaveCount(1);
    await expect(btn).toHaveText('Download untuk Windows');
    await expect(btn).toHaveAttribute('href', 'https://github.com/acme/winpad/releases/download/v2.0.0/WinPad-2.0.0-Setup.exe');
    await expect(page.getByTestId('dl-silent')).toHaveCount(0);
    await page.context().close();
  });

  test('same app on Linux gives the Linux asset, not the Windows one', async ({ browser }) => {
    const page = await pageAs(browser, 'linux');
    await page.goto('/app/acme--winpad/');
    await expect(page.getByTestId('dl-btn')).toHaveAttribute('href', /WinPad-2\.0\.0\.AppImage$/);
    await expect(page.getByTestId('dl-btn')).toHaveText('Download untuk Linux');
    await page.context().close();
  });

  test('picker silent: labelled asset list, no big button', async ({ browser }) => {
    const page = await pageAs(browser, 'windows');
    await page.goto('/app/acme--silentapp/');
    await expect(page.getByTestId('dl-silent')).toBeVisible();
    await expect(page.getByTestId('dl-btn')).toHaveCount(0);
    const list = page.getByTestId('asset-list');
    await expect(list.getByRole('link', { name: 'silentapp-win.exe' })).toHaveAttribute('href', /silentapp-win\.exe$/);
    await expect(list).toContainText('Windows');
    await expect(list).toContainText('macOS');
    await page.context().close();
  });

  test('macOS with separate arm64/x64 picks shows two labelled buttons', async ({ browser }) => {
    const page = await pageAs(browser, 'macos');
    await page.goto('/app/acme--macsplit/');
    const btns = page.getByTestId('dl-btn');
    await expect(btns).toHaveCount(2);
    await expect(btns.nth(0)).toContainText('Apple Silicon');
    await expect(btns.nth(0)).toHaveAttribute('href', /MacSplit-arm64\.dmg$/);
    await expect(btns.nth(1)).toContainText('Intel');
    await expect(btns.nth(1)).toHaveAttribute('href', /MacSplit-x64\.dmg$/);
    await page.context().close();
  });

  test('macOS with the same asset for both cells shows one button', async ({ browser }) => {
    const page = await pageAs(browser, 'macos');
    await page.goto('/app/acme--macuniversal/');
    const btns = page.getByTestId('dl-btn');
    await expect(btns).toHaveCount(1);
    await expect(btns).toHaveText('Download untuk macOS');
    await expect(btns).toHaveAttribute('href', /MacUniversal\.dmg$/);
    await page.context().close();
  });

  test('APK-only app: button on Android, plain "no build" message on Windows', async ({ browser }) => {
    const a = await pageAs(browser, 'android');
    await a.goto('/app/acme--androidonly/');
    await expect(a.getByTestId('dl-btn')).toHaveCount(1);
    await expect(a.getByTestId('dl-btn')).toHaveText('Download untuk Android');
    await expect(a.getByTestId('dl-btn')).toHaveAttribute('href', /androidonly-0\.9\.0\.apk$/);
    await a.context().close();

    const w = await pageAs(browser, 'windows');
    await w.goto('/app/acme--androidonly/');
    await expect(w.getByTestId('dl-btn')).toHaveCount(0);
    await expect(w.getByTestId('dl-nobuild')).toContainText('Belum ada build untuk OS Anda');
    await expect(w.getByTestId('asset-list')).toContainText('androidonly-0.9.0.apk');
    await w.context().close();
  });

  test('no build for visitor OS (Linux-only app on Windows and macOS)', async ({ browser }) => {
    for (const os of ['windows', 'macos'] as K[]) {
      const page = await pageAs(browser, os);
      await page.goto('/app/acme--linuxonly/');
      await expect(page.getByTestId('dl-btn')).toHaveCount(0);
      await expect(page.getByTestId('dl-nobuild')).toBeVisible();
      await expect(page.getByTestId('dl-silent')).toHaveCount(0);
      await page.context().close();
    }
  });

  test('slug with a dot resolves to its page on a plain static server', async ({ browser }) => {
    const page = await pageAs(browser, 'windows');
    await page.goto('/app/acme--dotted.js/');
    await expect(page.getByTestId('app-name')).toHaveText('Dotted.js');
    await expect(page.getByTestId('dl-btn')).toHaveAttribute('href', /dotted-Setup\.exe$/);
    await page.context().close();
  });

  test('stable/pre-release tabs and version selector switch the button target', async ({ browser }) => {
    const page = await pageAs(browser, 'windows');
    await page.goto('/app/acme--winpad/');
    await page.getByTestId('tab-pre').click();
    await expect(page.getByTestId('version-select')).toHaveValue('v2.1.0-beta');
    await expect(page.getByTestId('dl-btn')).toHaveAttribute('href', /WinPad-2\.1\.0-beta-Setup\.exe$/);
    await page.getByTestId('tab-stable').click();
    await page.getByTestId('version-select').selectOption('v1.0.0');
    await expect(page.getByTestId('dl-btn')).toHaveAttribute('href', /WinPad-1\.0\.0-Setup\.exe$/);
    await page.context().close();
  });

  test('trust block: facts only, SmartScreen guide link, never the words aman or safe', async ({ browser }) => {
    const page = await pageAs(browser, 'windows');
    await page.goto('/app/acme--winpad/');
    const trust = page.getByTestId('trust');
    await expect(trust).toContainText('C1-C4b');
    await expect(trust).toContainText('tidak kami verifikasi');
    await expect(page.getByTestId('guide-win')).toHaveAttribute('href', '/panduan/windows/');
    await expect(page.getByTestId('guide-mac')).toHaveCount(0);
    for (const url of ['/', '/app/acme--winpad/', '/tentang/', '/panduan/windows/', '/panduan/macos/', '/saya/']) {
      await page.goto(url);
      await page.waitForLoadState('networkidle');
      const text = await page.locator('body').innerText();
      expect(text, url).not.toMatch(/\b(aman|safe|safely)\b/i);
    }
    await page.context().close();
    const mac = await pageAs(browser, 'macos');
    await mac.goto('/app/acme--macsplit/');
    await expect(mac.getByTestId('guide-mac')).toHaveAttribute('href', '/panduan/macos/');
    await mac.context().close();
  });

  test('release notes render markdown but never inject raw HTML', async ({ browser }) => {
    const page = await pageAs(browser, 'windows');
    await page.goto('/app/acme--xssnotes/');
    const notes = page.getByTestId('release-notes');
    await expect(notes).toContainText('Plain');
    await expect(notes.locator('strong')).toHaveText('markdown bold');
    await expect(notes.locator('script, iframe, img, #rawbold, b')).toHaveCount(0);
    await expect(page.locator('[onerror]')).toHaveCount(0);
    await expect(page.locator('a[href^="javascript:" i]')).toHaveCount(0);
    expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();
    await page.context().close();
  });
});

test.describe('home', () => {
  test('default view hides developer apps; chip shows them', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('app-card').first()).toBeVisible();
    await expect(page.locator('[data-slug="acme--devtool"]')).toHaveCount(0);
    await page.getByTestId('search').fill('devtool');
    await expect(page.getByTestId('empty')).toBeVisible();
    await page.getByTestId('show-dev').click();
    await expect(page.locator('[data-slug="acme--devtool"]')).toHaveCount(1);
  });

  test('no trending tab while trending.json ready=false; default sort is latest', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('app-card').first()).toBeVisible();
    await expect(page.getByTestId('sort-trending')).toHaveCount(0);
    await expect(page.getByTestId('sort-latest')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('app-card').first()).toHaveAttribute('data-slug', 'acme--winpad');
    await page.getByTestId('sort-popular').click();
    await expect(page.getByTestId('sort-popular')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('app-card').first()).toHaveAttribute('data-slug', 'acme--winpad');
  });

  test('search filters client-side', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('search').fill('macsplit');
    await expect(page.getByTestId('app-card')).toHaveCount(1);
    await expect(page.getByTestId('app-card')).toHaveAttribute('data-slug', 'acme--macsplit');
    await page.getByTestId('search').fill('zzzzqqq');
    await expect(page.getByTestId('empty')).toBeVisible();
  });

  test('platform filter (Android)', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('plat-android').click();
    await expect(page.getByTestId('app-card')).toHaveCount(1);
    await expect(page.getByTestId('app-card')).toHaveAttribute('data-slug', 'acme--androidonly');
    await page.getByTestId('plat-all').click();
    await expect(page.getByTestId('app-card').first()).toBeVisible();
  });

  test('pagination: 48 per page, load more adds the rest', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('app-card')).toHaveCount(48);
    await page.getByTestId('load-more').click();
    await expect(page.getByTestId('app-card')).toHaveCount(68); // 69 fixtures minus 1 developer app
    await expect(page.getByTestId('load-more')).toHaveCount(0);
  });

  test('language toggle switches text and persists across reload', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('search')).toHaveAttribute('placeholder', /Cari nama/);
    await expect(page.locator('html')).toHaveAttribute('lang', 'id');
    await page.getByTestId('lang-en').click();
    await expect(page.getByTestId('search')).toHaveAttribute('placeholder', /Search name/);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await page.reload();
    await expect(page.getByTestId('search')).toHaveAttribute('placeholder', /Search name/);
    await page.getByTestId('lang-id').click();
    await expect(page.getByTestId('search')).toHaveAttribute('placeholder', /Cari nama/);
  });

  test('theme toggle flips data-theme', async ({ page }) => {
    await page.goto('/');
    const before = await page.locator('html').getAttribute('data-theme');
    await page.getByTestId('theme-toggle').click();
    const after = await page.locator('html').getAttribute('data-theme');
    expect(after).not.toBe(before);
  });
});

test.describe('App saya', () => {
  test('survives reload and can be removed', async ({ page }) => {
    await page.goto('/app/acme--winpad/');
    await page.getByTestId('add-mine').click();
    await expect(page.getByTestId('add-mine')).toHaveAttribute('aria-pressed', 'true');
    await page.goto('/saya/');
    await expect(page.getByTestId('mine-item')).toHaveCount(1);
    await page.reload();
    await expect(page.getByTestId('mine-item')).toHaveCount(1);
    await expect(page.getByTestId('mine-item')).toContainText('WinPad');
    await page.getByTestId('mine-remove').click();
    await expect(page.getByTestId('mine-empty')).toBeVisible();
    await page.reload();
    await expect(page.getByTestId('mine-empty')).toBeVisible();
  });

  test('works when localStorage throws', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173' });
    await ctx.addInitScript(() => {
      Object.defineProperty(window, 'localStorage', { get() { throw new Error('denied'); } });
    });
    const page = await ctx.newPage();
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto('/app/acme--winpad/');
    await page.getByTestId('add-mine').click();
    await page.goto('/saya/');
    await expect(page.getByTestId('mine-empty')).toBeVisible();
    expect(errors).toEqual([]);
    await ctx.close();
  });
});

test.describe('static pages', () => {
  test('/tentang has attribution and caveats; guides render', async ({ page }) => {
    await page.goto('/tentang/');
    const about = page.getByTestId('about');
    await expect(about).toContainText('Komi Store');
    await expect(about).toContainText('Apache-2.0');
    await expect(about).toContainText('komi-store-backend-data');
    await expect(about).toContainText('sering diam');
    await page.goto('/panduan/windows/');
    await expect(page.getByTestId('guide-win')).toContainText('SmartScreen');
    await page.goto('/panduan/macos/');
    await expect(page.getByTestId('guide-mac')).toContainText('Gatekeeper');
  });
});

test.describe('phone viewport 360x740', () => {
  const vp = { width: 360, height: 740 };
  for (const url of ['/', '/app/acme--macsplit/', '/app/acme--xssnotes/', '/tentang/', '/saya/']) {
    test(`no horizontal overflow on ${url}`, async ({ browser }) => {
      const page = await pageAs(browser, 'android', { viewport: vp });
      await page.goto(url);
      await page.waitForLoadState('networkidle');
      const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
      expect(m.sw).toBeLessThanOrEqual(m.iw);
      await page.context().close();
    });
  }

  test('home is usable and Android visitor gets the APK button', async ({ browser }) => {
    const page = await pageAs(browser, 'android', { viewport: vp });
    await page.goto('/');
    await expect(page.getByTestId('search')).toBeVisible();
    const box = await page.getByTestId('app-card').first().boundingBox();
    expect(box!.width).toBeGreaterThan(300);
    expect(box!.x + box!.width).toBeLessThanOrEqual(360);
    await page.goto('/app/acme--androidonly/');
    await expect(page.getByTestId('dl-btn')).toBeVisible();
    await page.context().close();
  });
});
