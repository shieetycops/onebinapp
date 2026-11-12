import { defineConfig } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

// Playwright 1.65 expects chromium rev 1254 which is not cached; reuse an installed one (no download).
function findChrome(): string | undefined {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const base = path.join(process.env.LOCALAPPDATA || '', 'ms-playwright');
  try {
    const dirs = fs.readdirSync(base).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse();
    for (const d of dirs) {
      const p = path.join(base, d, 'chrome-win64', 'chrome.exe');
      if (fs.existsSync(p)) return p;
    }
  } catch { /* fall through to Playwright default */ }
  return undefined;
}

// Guard: tests assume the fixture build (npm run build:test). Refuse to run against a real-data out/.
try {
  const cat = JSON.parse(fs.readFileSync(path.join(__dirname, 'out', 'data', 'catalog.json'), 'utf8'));
  if (cat.picker_sha256 !== 'fixture') throw new Error('out/ holds real data');
} catch (e) {
  throw new Error('Run "npm run build:test" first (out/ must contain the fixture build): ' + (e as Error).message);
}

export default defineConfig({
  testDir: './tests',
  testMatch: /.*\.spec\.ts/,
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 30_000,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:4173',
    launchOptions: { executablePath: findChrome() },
  },
  webServer: {
    command: 'node scripts/serve.mjs',
    url: 'http://localhost:4173',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
