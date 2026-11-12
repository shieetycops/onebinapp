import { test, expect } from '@playwright/test';

// Fixture meta.json: desktop 2026-03-04T23:30:00Z, ai 2026-05-06T00:10:00Z. The date shown is the build date in UTC,
// never the visitor's clock or time zone (23:30Z on the 4th is still the 4th, 00:10Z on the 6th is already the 6th).
const SECTIONS = [
  { url: '/', iso: '2026-03-04T23:30:00Z', id: '4 Maret 2026', en: '4 March 2026' },
  { url: '/ai/', iso: '2026-05-06T00:10:00Z', id: '6 Mei 2026', en: '6 May 2026' },
];

test.describe('footer: Katalog diperbarui', () => {
  for (const s of SECTIONS) {
    test(`${s.url} shows the build date (id and en)`, async ({ page }) => {
      await page.goto(s.url);
      const el = page.getByTestId('catalog-updated');
      await expect(el).toHaveText(`Katalog diperbarui: ${s.id}`);
      await expect(el).toHaveAttribute('data-iso', s.iso);
      await page.getByTestId('lang-en').click();
      await expect(el).toHaveText(`Catalog updated: ${s.en}`);
    });
  }

  test('the date does not depend on the visitor time zone or clock', async ({ browser }) => {
    for (const tz of ['Pacific/Kiritimati', 'Pacific/Pago_Pago']) {
      const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', timezoneId: tz });
      const page = await ctx.newPage();
      await page.clock.install({ time: new Date('2031-01-01T12:00:00Z') });
      await page.goto('/');
      await expect(page.getByTestId('catalog-updated')).toHaveText('Katalog diperbarui: 4 Maret 2026');
      await ctx.close();
    }
  });

  test('no date line when meta.json is missing (nothing invented)', async ({ page }) => {
    await page.route('**/data/meta.json', (r) => r.fulfill({ status: 404, body: '' }));
    await page.goto('/tentang/');
    await expect(page.locator('footer.foot')).toBeVisible();
    await expect(page.getByTestId('catalog-updated')).toHaveCount(0);
  });

  test('footer line fits a 360px phone without horizontal scroll', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', viewport: { width: 360, height: 740 } });
    const page = await ctx.newPage();
    for (const u of ['/', '/ai/']) {
      await page.goto(u);
      await expect(page.getByTestId('catalog-updated')).toBeVisible();
      const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
      expect(m.sw, u).toBeLessThanOrEqual(m.iw);
    }
    await ctx.close();
  });
});
