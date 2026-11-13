'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { Card } from '@/lib/types';
import type { Trending } from '@/lib/types';
import { loadCatalog, loadTrendingDoc } from '@/lib/data';
import { readMine, writeMine } from '@/lib/store';
import { AppCard } from './AppCard';
import { useI18n } from './Providers';
import { Eyebrow, Icon } from './Ui';

function TrendingBlock({ label, doc, loaded, id }: { label: string; doc: Trending | null; loaded: boolean; id: string }) {
  const { t } = useI18n();
  const x = t.trendAbout;
  if (!loaded) return null;
  const used = doc?.sources_used ?? [];
  const gh = used.includes('github_trending');
  return (
    <div data-testid={`trend-${id}`} data-ready={doc?.ready === true ? 'true' : 'false'}>
      <h3>{label}</h3>
      {!doc ? <p>{x.loadFail}</p> : (
        <>
          <p>{doc.ready ? x.ready : x.notReady}</p>
          <p>{x.used}:</p>
          <ul>
            {used.includes('stars_history') && <li data-testid="trend-src-history">{x.srcHistory}</li>}
            {gh && <li data-testid="trend-src-github">{x.srcGithub}</li>}
          </ul>
          {!gh && <p data-testid="trend-github-off">{x.ghOff}</p>}
        </>
      )}
    </div>
  );
}

export function About() {
  const { t } = useI18n();
  const [docs, setDocs] = useState<{ app: Trending | null; ai: Trending | null } | null>(null);
  useEffect(() => {
    Promise.all([loadTrendingDoc('trending'), loadTrendingDoc('trending-ai')]).then(([app, ai]) => setDocs({ app, ai }));
  }, []);
  const [lead, ...rest] = t.about.sections;
  const num = (i: number) => String(i + 1).padStart(2, '0');
  return (
    <div className="about" data-testid="about">
      <section className="app-hero about-hero">
        <Eyebrow>{t.chrome.aboutKicker.toUpperCase()}</Eyebrow>
        <h1 className="about-title">{t.about.title}</h1>
        {lead.p.map((p, i) => <p key={i} className="app-deck">{p}</p>)}
      </section>

      <div className="about-grid">
        {rest.map((sec, i) => (
          <section key={sec.h} className="about-card">
            <div className="section-stamp"><span>{num(i)}</span><h2>{sec.h}</h2></div>
            {sec.p.map((p, j) => <p key={j}>{p}</p>)}
          </section>
        ))}
      </div>

      <section className="source-panel about-links">
        <div className="source-icon"><Icon name="branch" /></div>
        <div>
          <Eyebrow>{t.chrome.aboutLinks.toUpperCase()}</Eyebrow>
          <p className="about-link-row">
            <a className="text-link" href="https://github.com/komi-store/komi-store" rel="noopener noreferrer">github.com/komi-store/komi-store <Icon name="arrowUpRight" /></a>
            <a className="text-link" href="https://github.com/komi-store/komi-store-backend-data" rel="noopener noreferrer">github.com/komi-store/komi-store-backend-data <Icon name="arrowUpRight" /></a>
            <a className="text-link" href="https://www.apache.org/licenses/LICENSE-2.0" rel="noopener noreferrer">Apache-2.0 <Icon name="arrowUpRight" /></a>
          </p>
        </div>
      </section>

      <section className="about-card about-trend" data-testid="about-trending">
        <div className="section-stamp"><span>{num(rest.length)}</span><h2>{t.trendAbout.title}</h2></div>
        <div className="trend-blocks">
          <TrendingBlock label={t.trendAbout.desktop} doc={docs?.app ?? null} loaded={!!docs} id="app" />
          <TrendingBlock label={t.trendAbout.ai} doc={docs?.ai ?? null} loaded={!!docs} id="ai" />
        </div>
        <p>{t.trendAbout.trendshift}</p>
        <p>{t.trendAbout.downloads}</p>
      </section>

      <div className="about-guides">
        <span className="picker-label">{t.chrome.aboutGuides.toUpperCase()}</span>
        <Link className="chip-link" href="/panduan/windows/">{t.nav.winGuide} <Icon name="arrowRight" size={14} /></Link>
        <Link className="chip-link" href="/panduan/macos/">{t.nav.macGuide} <Icon name="arrowRight" size={14} /></Link>
      </div>

      <div id="ai" data-testid="about-ai" className="about-ai">
        <section className="app-hero about-hero">
          <Eyebrow>{t.chrome.aboutAiKicker.toUpperCase()}</Eyebrow>
          <h2 className="about-title">{t.aboutAi.title}</h2>
        </section>
        <div className="about-grid">
          {t.aboutAi.sections.map((sec, i) => (
            <section key={sec.h} className="about-card">
              <div className="section-stamp"><span>{num(i)}</span><h2>{sec.h}</h2></div>
              {sec.p.map((p, j) => <p key={j}>{p}</p>)}
            </section>
          ))}
        </div>
        <p className="about-link-row">
          <a className="text-link" href="https://registry.modelcontextprotocol.io" rel="noopener noreferrer">registry.modelcontextprotocol.io <Icon name="arrowUpRight" /></a>
        </p>
      </div>
    </div>
  );
}

export function Guide({ kind }: { kind: 'win' | 'mac' }) {
  const { t } = useI18n();
  const g = kind === 'win' ? t.guideWin : t.guideMac;
  return (
    <div className="prose" data-testid={`guide-${kind}`}>
      <h1>{g.title}</h1>
      <p>{g.intro}</p>
      {kind === 'mac' && <p className="notice">{t.guideMac.chip}</p>}
      <ol>{g.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
      {kind === 'win' ? (
        <p className="note">{t.guideWin.note}</p>
      ) : (
        <p className="note"><a href="https://support.apple.com/en-us/102445" rel="noopener noreferrer">{t.guideMac.apple}</a></p>
      )}
    </div>
  );
}

export function Mine() {
  const { t } = useI18n();
  const [slugs, setSlugs] = useState<string[] | null>(null);
  const [apps, setApps] = useState<Card[]>([]);
  const [storageOk, setStorageOk] = useState(true);

  useEffect(() => {
    setSlugs(readMine());
    try { localStorage.getItem('jr-mine'); } catch { setStorageOk(false); }
    loadCatalog().then((c) => setApps(c.apps)).catch(() => {});
  }, []);

  function remove(slug: string) {
    const next = (slugs || []).filter((s) => s !== slug);
    setStorageOk(writeMine(next));
    setSlugs(next);
  }

  const bySlug = new Map(apps.map((a) => [a.slug, a]));
  const items = (slugs || []).map((s) => bySlug.get(s)).filter((a): a is Card => !!a);

  return (
    <div>
      <h1>{t.mine.title}</h1>
      <p className="note">{t.mine.note}</p>
      {!storageOk && <p className="notice">{t.mine.noStorage}</p>}
      {slugs && slugs.length === 0 && <p className="notice" data-testid="mine-empty">{t.mine.empty}</p>}
      <ul className="mine-list">
        {items.map((a, i) => (
          <li key={a.slug} className="mine-row" data-testid="mine-item">
            <AppCard app={a} index={i} />
            <button type="button" className="btn" onClick={() => remove(a.slug)} data-testid="mine-remove">{t.mine.remove}</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
