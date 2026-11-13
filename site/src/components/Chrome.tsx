'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useI18n } from './Providers';
import { loadMeta } from '@/lib/data';
import { fmtDay, fill } from '@/lib/format';
import { Icon } from './Ui';

function Brand({ label }: { label?: string }) {
  const { t } = useI18n();
  return (
    <Link className="wordmark" href="/" aria-label={label}>
      <span className="wordmark-symbol"><Icon name="blocks" /></span>
      <span>{t.brand}<span className="wordmark-period">.</span></span>
    </Link>
  );
}

export function Header() {
  const { t, lang, setLang, toggleTheme } = useI18n();
  const path = usePathname() || '';
  const inAi = path.startsWith('/ai');
  const cur = (p: string) => (path.replace(/\/$/, '') === p ? 'page' : undefined);
  const appActive = !inAi && !cur('/saya') && !cur('/tentang');
  return (
    <header className="masthead">
      <Brand label={t.brand} />
      <nav className="mast-nav" aria-label="Navigasi">
        <Link href="/" data-testid="switch-app" className={appActive ? 'current' : undefined} aria-current={appActive ? 'page' : undefined}>{t.ai.switchApp}</Link>
        <Link href="/ai/" data-testid="switch-ai" className={inAi ? 'current' : undefined} aria-current={inAi ? 'page' : undefined}>{t.ai.switchAi}</Link>
        <Link href="/saya/" aria-current={cur('/saya')} className={cur('/saya') ? 'current' : undefined}>{t.nav.mine}</Link>
        <Link href="/tentang/" aria-current={cur('/tentang')} className={cur('/tentang') ? 'current' : undefined}>{t.nav.about}</Link>
      </nav>
      <div className="masthead-actions">
        <div className="seg" role="group" aria-label={t.ui.lang}>
          <button type="button" data-testid="lang-id" aria-pressed={lang === 'id'} onClick={() => setLang('id')}>ID</button>
          <button type="button" data-testid="lang-en" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
        </div>
        <button type="button" className="theme-toggle" data-testid="theme-toggle" onClick={toggleTheme} aria-label={t.ui.theme} title={t.ui.theme}>
          <Icon name="moon" className="theme-moon" />
          <Icon name="sun" className="theme-sun" />
        </button>
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
      <div className="footer">
        <Brand />
        <span>{t.tagline}</span>
        {day ? <span data-testid="catalog-updated" data-iso={iso ?? ''}>{fill(t.footer.updated, { date: day })}</span> : <span />}
      </div>
      <div className="footer-notes">
        <p>{t.footer.line1}</p>
        <p>{t.footer.line2}</p>
        <p className="footer-links">
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
