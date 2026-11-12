import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const DATA = path.join(__dirname, 'fixtures', 'data');
const detail = (slug: string) => JSON.parse(fs.readFileSync(path.join(DATA, 'ai', slug + '.json'), 'utf8'));
const catalog = JSON.parse(fs.readFileSync(path.join(DATA, 'catalog-ai.json'), 'utf8')) as { entries: { slug: string }[] };
const BAD_WORD = /(?<![\w-])(aman|safe)(?![\w-])/i;
const TOOLS = ['claude-code', 'claude-desktop', 'cursor', 'vscode', 'codex'];
const ALPHA = '/ai/acme--alpha-mcp/';

async function bodyText(page: Page) {
  return page.evaluate(() => document.body.innerText);
}

test.describe('AI: list page', () => {
  test('cards show type badges and tool badges', async ({ page }) => {
    await page.goto('/ai/');
    const alpha = page.locator('[data-testid="ai-card"][data-slug="acme--alpha-mcp"]');
    await expect(alpha).toHaveCount(1);
    await expect(alpha.getByTestId('type-badge')).toHaveText(['MCP', 'Skill']);
    await expect(alpha.getByTestId('tool-badge')).toHaveText(['Claude Code', 'Claude Desktop', 'Cursor', 'VS Code', 'Codex']);
    const gamma = page.locator('[data-testid="ai-card"][data-slug="acme--gamma-plugin"]');
    await expect(gamma.getByTestId('type-badge')).toHaveText(['Plugin']);
    const delta = page.locator('[data-testid="ai-card"][data-slug="acme--delta-notool"]');
    await expect(delta.getByTestId('tool-badge')).toHaveCount(0);
  });

  test('filter by type, tool, category and search', async ({ page }) => {
    await page.goto('/ai/');
    await expect(page.getByTestId('ai-result-count')).toHaveText('61 entri');
    await page.getByTestId('type-plugin').click();
    await expect(page.getByTestId('ai-result-count')).toHaveText('2 entri'); // gamma + zeta
    await page.getByTestId('type-all').click();
    await page.getByTestId('type-skill').click();
    await expect(page.getByTestId('ai-result-count')).toHaveText('3 entri'); // alpha, beta, zeta
    await page.getByTestId('tool-codex').click();
    await expect(page.getByTestId('ai-result-count')).toHaveText('3 entri');
    await page.getByTestId('tool-cursor').click();
    await expect(page.getByTestId('ai-result-count')).toHaveText('2 entri'); // alpha, zeta
    await page.getByTestId('type-all').click();
    await page.getByTestId('tool-all').click();
    await page.getByTestId('aicat-files').click();
    await expect(page.getByTestId('ai-card')).toHaveCount(1);
    await expect(page.getByTestId('ai-card')).toHaveAttribute('data-slug', 'acme--beta-skill');
    await page.getByTestId('aicat-all').click();
    await page.getByTestId('ai-search').fill('zeta');
    await expect(page.getByTestId('ai-card')).toHaveCount(1);
    await page.getByTestId('ai-search').fill('qqqqnomatch');
    await expect(page.getByTestId('ai-empty')).toBeVisible();
  });

  test('sort by stars and by latest activity; pagination', async ({ page }) => {
    await page.goto('/ai/');
    await expect(page.getByTestId('ai-card').first()).toHaveAttribute('data-slug', 'acme--alpha-mcp'); // 9000 stars
    await page.getByTestId('aisort-latest').click();
    await expect(page.getByTestId('ai-card').first()).toHaveAttribute('data-slug', 'acme--zeta-all'); // 2026-11-11
    await expect(page.getByTestId('ai-card')).toHaveCount(48);
    await page.getByTestId('ai-load-more').click();
    await expect(page.getByTestId('ai-card')).toHaveCount(61);
  });

  test('trending tab only when ready=true', async ({ page, browser }) => {
    await page.goto('/ai/');
    await expect(page.getByTestId('aisort-stars')).toBeVisible();
    await expect(page.getByTestId('aisort-trending')).toHaveCount(0);
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173' });
    const p2 = await ctx.newPage();
    await p2.route('**/data/catalog-ai.json', async (route) => {
      const res = await route.fetch();
      const j = await res.json();
      j.entries[0].trending = { ready: true, d7: 5, d30: 9, rank: 1 };
      await route.fulfill({ response: res, json: j });
    });
    await p2.goto('/ai/');
    await expect(p2.getByTestId('aisort-trending')).toBeVisible();
    await ctx.close();
  });
});

test.describe('AI: detail page', () => {
  test('before choosing a tool no method is shown; each tool shows exactly ONE method', async ({ page }) => {
    await page.goto(ALPHA);
    await expect(page.getByTestId('install-method')).toHaveCount(0);
    await expect(page.getByTestId('oneclick-link')).toHaveCount(0);
    const expected: Record<string, string> = { 'claude-code': 'oneline', 'claude-desktop': 'snippet', cursor: 'oneclick', vscode: 'manual', codex: 'none' };
    for (const tool of TOOLS) {
      await page.getByTestId(`pick-${tool}`).click();
      await expect(page.getByTestId('install-method')).toHaveCount(1);
      await expect(page.getByTestId('install-method')).toHaveAttribute('data-kind', expected[tool]);
      await expect(page.getByTestId('install-method')).toHaveAttribute('data-tool', tool);
    }
  });

  test('oneclick is a link with the exact deeplink from the data', async ({ page }) => {
    const d = detail('acme--alpha-mcp');
    await page.goto(ALPHA);
    await page.getByTestId('pick-cursor').click();
    const link = page.getByTestId('oneclick-link');
    await expect(link).toHaveCount(1);
    expect(await link.getAttribute('href')).toBe(d.install.cursor.mcp.url);
    await expect(page.getByTestId('install-text')).toHaveCount(0);
    await expect(page.getByTestId('method-source')).toHaveAttribute('href', d.install.cursor.mcp.source_url);
    await expect(page.getByTestId('method-source')).toHaveText('sumber: dokumentasi resmi');
  });

  test('oneline: command shown and copy button copies the exact text', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', permissions: ['clipboard-read', 'clipboard-write'] });
    const page = await ctx.newPage();
    const d = detail('acme--alpha-mcp');
    await page.goto(ALPHA);
    await page.getByTestId('pick-claude-code').click();
    const want = d.install['claude-code'].mcp.text as string;
    expect(await page.getByTestId('install-text').textContent()).toBe(want);
    await page.getByTestId('copy-btn').click();
    await expect(page.getByTestId('copy-btn')).toHaveText('Tersalin');
    expect((await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g, '\n')).toBe(want);
    await ctx.close();
  });

  test('snippet: multi-line config copied exactly, per-OS paths shown as given', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', permissions: ['clipboard-read', 'clipboard-write'] });
    const page = await ctx.newPage();
    const d = detail('acme--alpha-mcp');
    await page.goto(ALPHA);
    await page.getByTestId('pick-claude-desktop').click();
    const m = d.install['claude-desktop'].mcp;
    await page.getByTestId('copy-btn').click();
    // Windows clipboard stores line breaks as CRLF; the page text node itself is compared exactly below.
    expect((await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g, '\n')).toBe(m.text);
    expect(await page.getByTestId('install-text').textContent()).toBe(m.text);
    const paths = page.getByTestId('snippet-paths');
    for (const p of Object.values(m.file_path_by_os) as string[]) await expect(paths).toContainText(p);
    await ctx.close();
  });

  test('snippet with a documented file_path shows it (and the label) even without per-OS paths', async ({ page }) => {
    const d = detail('acme--gamma-plugin');
    await page.goto('/ai/acme--gamma-plugin/');
    await page.getByTestId('pick-vscode').click();
    await expect(page.getByTestId('install-method')).toHaveAttribute('data-kind', 'snippet');
    await expect(page.getByTestId('snippet-file')).toHaveText(d.install.vscode.plugin.file_path);
    await expect(page.getByTestId('method-label')).toHaveText(d.install.vscode.plugin.label);
    await expect(page.getByTestId('snippet-paths')).toContainText('tidak terdokumentasi');
  });

  test('copy button passes the exact string to navigator.clipboard.writeText (stubbed, OS-independent)', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173' });
    await ctx.addInitScript(() => {
      (window as unknown as { __copied: string[] }).__copied = [];
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: async (s: string) => { (window as unknown as { __copied: string[] }).__copied.push(s); } },
        configurable: true,
      });
    });
    const page = await ctx.newPage();
    const d = detail('acme--alpha-mcp');
    await page.goto(ALPHA);
    await page.getByTestId('pick-claude-desktop').click();
    await page.getByTestId('copy-btn').click();
    const got = await page.evaluate(() => (window as unknown as { __copied: string[] }).__copied);
    expect(got).toEqual([d.install['claude-desktop'].mcp.text]);
    await ctx.close();
  });

  test('snippet without per-OS path says the OS path is not documented', async ({ page }) => {
    await page.goto('/ai/acme--beta-skill/');
    await page.getByTestId('pick-codex').click();
    await expect(page.getByTestId('install-method')).toHaveAttribute('data-kind', 'snippet');
    await expect(page.getByTestId('snippet-paths')).toContainText('tidak terdokumentasi');
  });

  test('manual renders numbered steps', async ({ page }) => {
    await page.goto(ALPHA);
    await page.getByTestId('pick-vscode').click();
    const steps = page.getByTestId('manual-steps');
    expect(await steps.evaluate((e) => e.tagName)).toBe('OL');
    await expect(steps.locator('li')).toHaveCount(3);
  });

  test('best method across types: claude-code on alpha picks mcp oneline over skill manual', async ({ page }) => {
    await page.goto(ALPHA);
    await page.getByTestId('pick-claude-code').click();
    await expect(page.getByTestId('install-method')).toContainText('MCP');
    await expect(page.getByTestId('install-text')).toContainText('claude mcp add alpha');
  });

  test('access box is before the install box, with exact values and disclaimer', async ({ page }) => {
    const d = detail('acme--alpha-mcp');
    await page.goto(ALPHA);
    await expect(page.getByTestId('install-box')).toBeVisible();
    const order = await page.evaluate(() => {
      const a = document.querySelector('[data-testid="access-box"]')!;
      const b = document.querySelector('[data-testid="install-box"]')!;
      const pr = document.querySelector('[data-testid="prereq-box"]')!;
      return { accessBeforeInstall: !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING), prereqBeforeAccess: !!(pr.compareDocumentPosition(a) & Node.DOCUMENT_POSITION_FOLLOWING) };
    });
    expect(order).toEqual({ accessBeforeInstall: true, prereqBeforeAccess: true });
    await expect(page.getByTestId('access-files')).toHaveText(d.access.files);
    await expect(page.getByTestId('access-terminal')).toContainText(d.access.terminal);
    await expect(page.getByTestId('access-network')).toHaveText(d.access.network);
    await expect(page.getByTestId('access-api_keys')).toContainText(d.access.api_keys);
    await expect(page.getByTestId('api-keys-list')).toContainText('ALPHA_KEY');
    await expect(page.getByTestId('api-keys-list')).toContainText('wajib');
    await expect(page.getByTestId('access-disclaimer')).toHaveText(d.access.disclaimer);
    await expect(page.getByTestId('prereq-box')).toContainText('Node.js');
  });

  test('entry without evidence shows tidak diketahui in all four fields', async ({ page }) => {
    await page.goto('/ai/acme--beta-skill/');
    await expect(page.getByTestId('access-box')).toBeVisible();
    for (const f of ['files', 'terminal', 'network', 'api_keys']) {
      await expect(page.getByTestId(`access-${f}`)).toHaveText('tidak diketahui');
    }
    await expect(page.getByTestId('access-disclaimer')).toHaveText('Ini daftar apa yang diminta manifest, bukan penilaian keamanan.');
  });

  test('entries with no tool, or only none methods, show the none message for every tool', async ({ page }) => {
    for (const slug of ['acme--delta-notool', 'acme--zeta-all']) {
      await page.goto(`/ai/${slug}/`);
      for (const tool of TOOLS) {
        await page.getByTestId(`pick-${tool}`).click();
        await expect(page.getByTestId('install-method')).toHaveCount(1);
        await expect(page.getByTestId('install-none')).toHaveText('belum ada cara pasang terdokumentasi untuk tool ini');
        await expect(page.getByTestId('install-text')).toHaveCount(0);
        await expect(page.getByTestId('oneclick-link')).toHaveCount(0);
        await expect(page.getByTestId('method-source')).toHaveCount(0);
      }
      await expect(page.getByTestId('access-box')).toBeVisible();
    }
  });

  test('tool choice is remembered (localStorage) and survives reload', async ({ page }) => {
    await page.goto(ALPHA);
    await page.getByTestId('pick-vscode').click();
    await page.reload();
    await expect(page.getByTestId('pick-vscode')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('install-method')).toHaveAttribute('data-tool', 'vscode');
    await page.goto('/ai/acme--beta-skill/');
    await expect(page.getByTestId('pick-vscode')).toHaveAttribute('aria-pressed', 'true');
  });

  test('works when localStorage throws', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173' });
    await ctx.addInitScript(() => {
      Object.defineProperty(window, 'localStorage', { get() { throw new Error('denied'); } });
    });
    const page = await ctx.newPage();
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto(ALPHA);
    await page.getByTestId('pick-cursor').click();
    await expect(page.getByTestId('install-method')).toHaveAttribute('data-kind', 'oneclick');
    expect(errors).toEqual([]);
    await ctx.close();
  });
});

test.describe('AI: untrusted text', () => {
  test('hostile description and name render as plain text, no injected HTML', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    for (const url of ['/ai/', '/ai/acme--evil-desc/']) {
      await page.goto(url);
      await page.waitForLoadState('networkidle');
      if (url !== '/ai/') {
        await page.getByTestId('pick-claude-code').click();
        await expect(page.getByTestId('method-note')).toContainText('<i id="rawital">note</i>');
      }
      expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();
      await expect(page.locator('#rawbold, #evilname, #rawital')).toHaveCount(0);
      await expect(page.locator('main script, main iframe')).toHaveCount(0);
      await expect(page.locator('main img[onerror]')).toHaveCount(0);
      expect(await page.locator('main').innerText()).toContain('<b id="rawbold">raw bold</b>');
    }
    expect(errors).toEqual([]);
  });

  test('no "aman" or "safe" words on any /ai page, with every tool picked', async ({ page }) => {
    await page.goto('/ai/');
    expect(await bodyText(page)).not.toMatch(BAD_WORD);
    for (const e of catalog.entries.slice(0, 8)) {
      await page.goto(`/ai/${e.slug}/`);
      await expect(page.getByTestId('access-box')).toBeVisible();
      expect(await bodyText(page)).not.toMatch(BAD_WORD);
      for (const tool of TOOLS) {
        await page.getByTestId(`pick-${tool}`).click();
        expect(await bodyText(page)).not.toMatch(BAD_WORD);
      }
    }
    await page.goto('/ai/');
    await page.getByTestId('lang-en').click();
    expect(await bodyText(page)).not.toMatch(BAD_WORD);
    await page.goto('/tentang/');
    await expect(page.getByTestId('about-ai')).toBeVisible();
    expect(await page.getByTestId('about-ai').innerText()).not.toMatch(BAD_WORD);
  });
});

test.describe('AI: navigation, i18n, about', () => {
  test('nav switch moves between App desktop and Untuk AI tools', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('switch-app')).toHaveAttribute('aria-current', 'page');
    await page.getByTestId('switch-ai').click();
    await expect(page).toHaveURL(/\/ai\/$/);
    await expect(page.getByTestId('switch-ai')).toHaveAttribute('aria-current', 'page');
    await expect(page.getByTestId('ai-card').first()).toBeVisible();
    await page.getByTestId('ai-card').first().click();
    await expect(page.getByTestId('switch-ai')).toHaveAttribute('aria-current', 'page');
    await page.getByTestId('switch-app').click();
    await expect(page).toHaveURL(/localhost:4173\/$/);
    await expect(page.getByTestId('app-card').first()).toBeVisible();
  });

  test('language toggle changes the AI page text; the fixed none sentence stays', async ({ page }) => {
    await page.goto(ALPHA);
    await expect(page.getByRole('heading', { name: 'Yang bisa diakses' })).toBeVisible();
    await page.getByTestId('lang-en').click();
    await expect(page.getByRole('heading', { name: 'What it can access' })).toBeVisible();
    await expect(page.getByTestId('switch-ai')).toHaveText('For AI tools');
    await page.getByTestId('pick-codex').click();
    await expect(page.getByTestId('install-none')).toHaveText('belum ada cara pasang terdokumentasi untuk tool ini');
    await page.goto('/ai/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Tools for your AI assistant');
    await page.getByTestId('lang-id').click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Tool untuk asisten AI Anda');
  });

  test('/tentang has the AI section: sources, R1-R8, trending and Trendshift notes', async ({ page }) => {
    await page.goto('/tentang/');
    const ai = page.getByTestId('about-ai');
    await expect(ai).toContainText('MCP Registry resmi');
    await expect(ai).toContainText('pencarian topik GitHub');
    for (const r of ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8']) await expect(ai).toContainText(r);
    await expect(ai).toContainText('github.com/trending');
    await expect(ai).toContainText('tidak di-scrape');
    await expect(ai).toContainText('Trendshift');
    await expect(ai).toContainText('berbayar');
    await expect(ai).toContainText('melarang redistribusi');
    await expect(page.getByTestId('about')).toContainText('sering diam'); // part 1 text still there
  });
});

test.describe('AI: phone viewport 360x740', () => {
  const vp = { width: 360, height: 740 };
  for (const url of ['/ai/', ALPHA, '/ai/acme--evil-desc/', '/ai/acme--delta-notool/', '/tentang/']) {
    test(`no horizontal overflow on ${url}`, async ({ browser }) => {
      const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', viewport: vp });
      const page = await ctx.newPage();
      await page.goto(url);
      await page.waitForLoadState('networkidle');
      if (url.startsWith('/ai/acme')) {
        for (const tool of TOOLS) {
          await page.getByTestId(`pick-${tool}`).click();
          const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
          expect(m.sw, `tool ${tool}`).toBeLessThanOrEqual(m.iw);
        }
      }
      const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
      expect(m.sw).toBeLessThanOrEqual(m.iw);
      await ctx.close();
    });
  }

  test('nav switch is reachable and cards fit on a phone', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', viewport: vp });
    const page = await ctx.newPage();
    await page.goto('/');
    await page.getByTestId('switch-ai').click();
    const box = await page.getByTestId('ai-card').first().boundingBox();
    expect(box!.x + box!.width).toBeLessThanOrEqual(360);
    await ctx.close();
  });
});

test.describe('AI: Cara pakai (usage panel)', () => {
  const GAMMA = '/ai/acme--gamma-plugin/';

  test('no tool picked: only a hint; picking a tool shows all sections in order', async ({ page }) => {
    await page.goto(ALPHA);
    await expect(page.getByTestId('use-pick-hint')).toBeVisible();
    await expect(page.getByTestId('use-after')).toHaveCount(0);
    await page.getByTestId('pick-claude-code').click();
    await expect(page.getByTestId('use-pick-hint')).toHaveCount(0);
    const heads = await page.getByTestId('usage-box').locator('h2, h3').allInnerTexts();
    expect(heads).toEqual(['Cara pakai', 'Setelah terpasang', 'Yang bisa dilakukan', 'Contoh pakai', 'Pengaturan yang perlu diisi', 'Cara mencopot']);
    const order = await page.evaluate(() => {
      const a = document.querySelector('[data-testid=install-box]')!.compareDocumentPosition(document.querySelector('[data-testid=usage-box]')!);
      return !!(a & Node.DOCUMENT_POSITION_FOLLOWING);
    });
    expect(order).toBe(true);
  });

  test('MCP + Claude Code: steps, tool list, README examples, settings, uninstall uses the install name', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', permissions: ['clipboard-read', 'clipboard-write'] });
    const page = await ctx.newPage();
    await page.goto(ALPHA);
    await page.getByTestId('pick-claude-code').click();
    await expect(page.getByTestId('use-after')).toContainText('claude mcp list');
    await expect(page.getByTestId('use-after-source')).toHaveAttribute('href', 'https://code.claude.com/docs/en/mcp');
    await expect(page.getByTestId('use-can')).toContainText('alpha_search');
    await expect(page.getByTestId('use-can')).toContainText('Search the alpha index.');
    await expect(page.getByTestId('use-examples')).toHaveAttribute('data-auto', '0');
    await expect(page.getByTestId('use-example-label')).toHaveText('contoh dari README repo');
    await expect(page.getByTestId('use-example')).toHaveCount(2);
    await expect(page.getByTestId('use-settings')).toContainText('ALPHA_KEY');
    await expect(page.getByTestId('use-settings')).toContainText('Create it in the Alpha dashboard');
    await expect(page.getByTestId('use-settings')).toContainText('ALPHA_REGION');
    await expect(page.getByTestId('use-settings')).toContainText('tidak tersedia di repo');
    await expect(page.getByTestId('use-settings-where')).toContainText('~/.claude.json');
    const install = await page.getByTestId('install-text').innerText();
    const name = install.match(/^claude mcp add (\S+)/)![1];
    await expect(page.getByTestId('use-remove').getByTestId('use-cmd')).toHaveText(`claude mcp remove ${name}`);
    await page.getByTestId('use-copy').click();
    expect((await page.evaluate(() => navigator.clipboard.readText())).trim()).toBe(`claude mcp remove ${name}`);
    await ctx.close();
  });

  test('a cell the official docs do not cover says so, without a link or invented steps', async ({ page }) => {
    await page.goto(ALPHA);
    await page.getByTestId('pick-cursor').click();
    await expect(page.getByTestId('use-remove-na')).toContainText('tidak terdokumentasi');
    await expect(page.getByTestId('use-settings-where-na')).toContainText('tidak terdokumentasi');
    await expect(page.getByTestId('use-remove-source')).toHaveCount(0);
  });

  test('plugin: slash commands, agents and hooks; auto examples are labelled; no settings section', async ({ page }) => {
    await page.goto(GAMMA);
    await page.getByTestId('pick-claude-code').click();
    await expect(page.getByTestId('use-can')).toContainText('/plan');
    await expect(page.getByTestId('use-can')).toContainText('Plan the work');
    await expect(page.getByTestId('use-can')).toContainText('reviewer');
    await expect(page.getByTestId('use-can')).toContainText('PreToolUse');
    await expect(page.getByTestId('use-can')).toContainText('echo hello');
    await expect(page.getByTestId('use-examples')).toHaveAttribute('data-auto', '1');
    await expect(page.getByTestId('use-example-label')).toHaveText('contoh otomatis, belum diuji');
    await expect(page.getByTestId('use-settings')).toHaveCount(0);
    await expect(page.getByTestId('use-settings-na')).toHaveCount(0);
    await expect(page.getByTestId('use-remove')).toContainText('claude plugin uninstall gamma@gamma-plugin');
  });

  test('missing data: "tidak tersedia di repo" plus the exact README link, nothing invented', async ({ page }) => {
    await page.goto('/ai/acme--beta-skill/');
    await page.getByTestId('pick-claude-code').click();
    await expect(page.getByTestId('use-can-na')).toContainText('tidak tersedia di repo');
    await expect(page.getByTestId('use-examples-na')).toContainText('tidak tersedia di repo');
    await expect(page.getByTestId('use-can-na').getByTestId('use-readme-link')).toHaveAttribute('href', 'https://github.com/acme/beta-skill#readme');
    await expect(page.getByTestId('use-after-na')).toContainText('tidak terdokumentasi');
  });

  test('hostile repo text in the usage panel is plain text', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await page.goto('/ai/acme--evil-desc/');
    await page.getByTestId('pick-claude-code').click();
    await expect(page.getByTestId('use-can')).toContainText('<script>window.__xss=3</script>');
    await expect(page.getByTestId('use-examples')).toContainText('<b id="rawex">this</b> **now** [click](javascript:window.__xss=5)');
    await expect(page.getByTestId('use-settings')).toContainText('<i id="rawwhere">get it here</i>');
    await expect(page.getByTestId('use-after')).toContainText('<b id="rawstep">step</b>');
    await expect(page.locator('#rawname, #rawex, #rawwhere, #rawstep')).toHaveCount(0);
    await expect(page.locator('main script, main iframe, main img[onerror]')).toHaveCount(0);
    await expect(page.getByTestId('usage-box').locator('a[href^="javascript"]')).toHaveCount(0);
    expect(await page.evaluate(() => (window as unknown as { __xss?: number }).__xss)).toBeUndefined();
    expect(errors).toEqual([]);
  });

  test('English labels', async ({ page }) => {
    await page.goto(GAMMA);
    await page.getByTestId('lang-en').click();
    await page.getByTestId('pick-claude-code').click();
    await expect(page.getByTestId('use-example-label')).toHaveText('auto-generated example, not tested');
    const heads = await page.getByTestId('usage-box').locator('h2, h3').allInnerTexts();
    expect(heads).toEqual(['How to use', 'After installing', 'What it can do', 'Example prompts', 'How to remove']);
  });

  test('phone viewport: no horizontal overflow with the usage panel open', async ({ browser }) => {
    const ctx = await browser.newContext({ baseURL: 'http://localhost:4173', viewport: { width: 360, height: 740 } });
    const page = await ctx.newPage();
    for (const url of [ALPHA, GAMMA, '/ai/acme--evil-desc/']) {
      await page.goto(url);
      await page.getByTestId('pick-claude-code').click();
      await expect(page.getByTestId('usage-box')).toBeVisible();
      const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
      expect(m.sw, url).toBeLessThanOrEqual(m.iw);
    }
    await ctx.close();
  });
});
