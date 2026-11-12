// throwaway smoke check of the REAL build in out/ (not part of npm test). Run: node scripts/smoke-real.mjs
import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import fs from 'node:fs'; import path from 'node:path';
const base = path.join(process.env.LOCALAPPDATA, 'ms-playwright');
const dir = fs.readdirSync(base).filter(d => /^chromium-\d+$/.test(d)).sort().reverse()[0];
const exe = path.join(base, dir, 'chrome-win64', 'chrome.exe');
const srv = spawn('node', ['scripts/serve.mjs'], { stdio: 'ignore' });
const U = { windows: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
  macos: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36' };
let ok = true; const log = (...a) => console.log(...a);
try {
  for (let i = 0; i < 40; i++) { try { if ((await fetch('http://localhost:4173/')).ok) break; } catch {} await new Promise(r => setTimeout(r, 500)); }
  const b = await chromium.launch({ executablePath: exe });
  for (const [os, ua] of Object.entries(U)) {
    const ctx = await b.newContext({ userAgent: ua }); const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', e => errs.push(String(e))); p.on('response', r => { if (r.status() >= 400) errs.push(r.status() + ' ' + r.url()); });
    await p.goto('http://localhost:4173/'); await p.waitForSelector('[data-testid], article, .card', { timeout: 20000 }).catch(() => {});
    await p.waitForTimeout(1500);
    const info = await p.evaluate(() => ({ cards: document.querySelectorAll('[data-testid="app-card"]').length, text: document.body.innerText.slice(0, 200).replace(/\n/g, ' | ') }));
    log(os, 'home', JSON.stringify(info));
    for (const slug of ['anomalyco--opencode', 'rem0o--fancontrol.releases']) {
      await p.goto(`http://localhost:4173/app/${slug}/`); await p.waitForTimeout(1500);
      const t = await p.evaluate(() => ({ h1: document.querySelector('h1')?.innerText, dl: [...document.querySelectorAll('a')].filter(a => /releases\/download/.test(a.href)).length, body: document.body.innerText.length, aman: /\b(aman|safe)\b/i.test(document.body.innerText) }));
      log(os, slug, JSON.stringify(t)); if (!t.h1 || t.aman) ok = false;
    }
    log(os, 'errors', errs.length, errs.slice(0, 3)); if (errs.length) ok = false; if (info.cards < 1) ok = false;
    await ctx.close();
  }
  // --- Untuk AI tools: /ai and two /ai/<slug> pages (one with tools, one with no documented method) ---
  {
    const BAD = /(?<![\w-])(aman|safe)(?![\w-])/i;
    const ctx = await b.newContext({ userAgent: U.windows }); const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', e => errs.push(String(e))); p.on('response', r => { if (r.status() >= 400) errs.push(r.status() + ' ' + r.url()); });
    await p.goto('http://localhost:4173/ai/'); await p.waitForSelector('[data-testid="ai-card"]', { timeout: 20000 }).catch(() => {});
    const home = await p.evaluate(() => ({ cards: document.querySelectorAll('[data-testid="ai-card"]').length, types: document.querySelectorAll('[data-testid="type-badge"]').length, count: document.querySelector('[data-testid="ai-result-count"]')?.textContent, text: document.body.innerText }));
    log('ai home', JSON.stringify({ cards: home.cards, typeBadges: home.types, count: home.count, badWord: BAD.test(home.text) }));
    if (home.cards < 1 || home.types < 1 || BAD.test(home.text)) ok = false;
    for (const [slug, tool, want] of [['morluto--rea', 'cursor', 'oneclick'], ['open-webui--open-webui', 'claude-code', 'none']]) {
      await p.evaluate(() => localStorage.removeItem('jr-ai-tool')); // remembered choice would pre-select a tool
      await p.goto(`http://localhost:4173/ai/${slug}/`); await p.waitForSelector('[data-testid="access-box"]', { timeout: 20000 }).catch(() => {});
      const before = await p.evaluate(() => ({ h1: document.querySelector('h1')?.innerText, access: !!document.querySelector('[data-testid="access-box"]'), methods: document.querySelectorAll('[data-testid="install-method"]').length }));
      await p.click(`[data-testid="pick-${tool}"]`);
      const after = await p.evaluate(() => { const m = document.querySelector('[data-testid="install-method"]'); return { methods: document.querySelectorAll('[data-testid="install-method"]').length, kind: m?.getAttribute('data-kind'), href: document.querySelector('[data-testid="oneclick-link"]')?.getAttribute('href') || null, none: document.querySelector('[data-testid="install-none"]')?.textContent || null, text: document.body.innerText }; });
      const bad = BAD.test(after.text);
      log('ai', slug, JSON.stringify({ h1: before.h1, access: before.access, methodsBefore: before.methods, methodsAfter: after.methods, kind: after.kind, href: after.href && after.href.slice(0, 60), none: after.none, badWord: bad }));
      if (!before.h1 || !before.access || before.methods !== 0 || after.methods !== 1 || after.kind !== want || bad) ok = false;
    }
    log('ai errors', errs.length, errs.slice(0, 3)); if (errs.length) ok = false;
    await ctx.close();
  }
  await b.close();
} finally { srv.kill(); }
log(ok ? 'SMOKE OK' : 'SMOKE PROBLEM'); process.exit(ok ? 0 : 1);
