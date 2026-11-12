'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useI18n } from './Providers';
import { loadMeta } from '@/lib/data';
import { fmtDay, fill } from '@/lib/format';

export function Header() {
  const { t, lang, setLang, theme, toggleTheme } = useI18n();
  const inAi = (usePathname() || '').startsWith('/ai');
  return (
    <header className="top">
      <div className="top-in">
        <Link href="/" className="brand" aria-label={t.brand}>
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 20" width="32" height="20"><path d="M1 17h30M4 17V9m24 8V9M4 9C10 1 22 1 28 9" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>
          </span>
          <span className="brand-name">{t.brand}</span>
        </Link>
        <nav className="sect" aria-label={t.ai.switchLabel}>
          <Link href="/" data-testid="switch-app" aria-current={inAi ? undefined : 'page'}>{t.ai.switchApp}</Link>
          <Link href="/ai/" data-testid="switch-ai" aria-current={inAi ? 'page' : undefined}>{t.ai.switchAi}</Link>
        </nav>
        <nav className="nav" aria-label="Navigasi">
          <Link href="/">{t.nav.home}</Link>
          <Link href="/saya/">{t.nav.mine}</Link>
          <Link href="/tentang/">{t.nav.about}</Link>
        </nav>
        <div className="tools">
          <div className="seg" role="group" aria-label={t.ui.lang}>
            <button type="button" data-testid="lang-id" aria-pressed={lang === 'id'} onClick={() => setLang('id')}>ID</button>
            <button type="button" data-testid="lang-en" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
          </div>
          <button type="button" className="icon-btn" data-testid="theme-toggle" onClick={toggleTheme} aria-label={t.ui.theme} title={theme === 'dark' ? t.ui.light : t.ui.dark}>
            {theme === 'dark' ? '☀' : '☾'}
          </button>
        </div>
      </div>
    </header>
  );
}

export function Footer() {
  const { t, lang } = useI18n();
  const inAi = (usePathname() || '').startsWith('/ai');
  const [iso, setIso] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    loadMeta().then((m) => { if (live) setIso((inAi ? m?.ai : m?.desktop) || null); });
    return () => { live = false; };
  }, [inAi]);
  const day = fmtDay(iso, lang);
  return (
    <footer className="foot">
      <div className="wrap">
        {day && <p data-testid="catalog-updated" data-iso={iso ?? ''}>{fill(t.footer.updated, { date: day })}</p>}
        <p>{t.footer.line1}</p>
        <p>{t.footer.line2}</p>
        <p className="foot-links">
          <Link href="/tentang/">{t.footer.about}</Link>
          <Link href="/panduan/windows/">{t.nav.winGuide}</Link>
          <Link href="/panduan/macos/">{t.nav.macGuide}</Link>
          <a href="https://github.com/komi-store/komi-store" rel="noopener noreferrer">Komi Store</a>
          <a href="https://github.com/komi-store/komi-store-backend-data" rel="noopener noreferrer">komi-store-backend-data</a>
        </p>
      </div>
    </footer>
  );
}
