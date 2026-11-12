'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { Card } from '@/lib/types';
import type { Trending } from '@/lib/types';
import { loadCatalog, loadTrendingDoc } from '@/lib/data';
import { readMine, writeMine } from '@/lib/store';
import { AppCard } from './AppCard';
import { useI18n } from './Providers';

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
  return (
    <div className="prose" data-testid="about">
      <h1>{t.about.title}</h1>
      {t.about.sections.map((s) => (
        <section key={s.h}>
          <h2>{s.h}</h2>
          {s.p.map((p, i) => <p key={i}>{p}</p>)}
        </section>
      ))}
      <p>
        <a href="https://github.com/komi-store/komi-store" rel="noopener noreferrer">github.com/komi-store/komi-store</a> &middot;{' '}
        <a href="https://github.com/komi-store/komi-store-backend-data" rel="noopener noreferrer">github.com/komi-store/komi-store-backend-data</a> &middot;{' '}
        <a href="https://www.apache.org/licenses/LICENSE-2.0" rel="noopener noreferrer">Apache-2.0</a>
      </p>
      <section data-testid="about-trending">
        <h2>{t.trendAbout.title}</h2>
        <TrendingBlock label={t.trendAbout.desktop} doc={docs?.app ?? null} loaded={!!docs} id="app" />
        <TrendingBlock label={t.trendAbout.ai} doc={docs?.ai ?? null} loaded={!!docs} id="ai" />
        <p>{t.trendAbout.trendshift}</p>
        <p>{t.trendAbout.downloads}</p>
      </section>
      <p><Link href="/panduan/windows/">{t.nav.winGuide}</Link> &middot; <Link href="/panduan/macos/">{t.nav.macGuide}</Link></p>
      <div id="ai" data-testid="about-ai">
        <h1>{t.aboutAi.title}</h1>
        {t.aboutAi.sections.map((s) => (
          <section key={s.h}>
            <h2>{s.h}</h2>
            {s.p.map((p, i) => <p key={i}>{p}</p>)}
          </section>
        ))}
        <p>
          <a href="https://registry.modelcontextprotocol.io" rel="noopener noreferrer">registry.modelcontextprotocol.io</a>
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
      <ul className="grid" style={{ marginTop: 12 }}>
        {items.map((a) => (
          <li key={a.slug} className="mine-row" data-testid="mine-item">
            <AppCard app={a} />
            <button type="button" className="btn" onClick={() => remove(a.slug)} data-testid="mine-remove">{t.mine.remove}</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
