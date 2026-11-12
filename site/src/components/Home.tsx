'use client';

import { useEffect, useMemo, useState } from 'react';
import type { Card, OS } from '@/lib/types';
import { CATEGORIES, PLATFORMS } from '@/lib/types';
import { loadCatalog, loadTrendingReady } from '@/lib/data';
import { fill } from '@/lib/format';
import { AppCard } from './AppCard';
import { useI18n } from './Providers';

const PAGE = 48;
type Sort = 'popular' | 'latest' | 'trending';

export default function Home() {
  const { t } = useI18n();
  const [apps, setApps] = useState<Card[] | null>(null);
  const [err, setErr] = useState(false);
  const [trendingReady, setTrendingReady] = useState(false);
  const [qRaw, setQRaw] = useState('');
  const [q, setQ] = useState('');
  const [platform, setPlatform] = useState<OS | 'all'>('all');
  const [category, setCategory] = useState<string>('all');
  const [showDev, setShowDev] = useState(false);
  const [sort, setSort] = useState<Sort>('latest');
  const [limit, setLimit] = useState(PAGE);

  useEffect(() => {
    loadCatalog().then((c) => setApps(c.apps)).catch(() => setErr(true));
    loadTrendingReady().then(setTrendingReady);
  }, []);

  useEffect(() => {
    const id = setTimeout(() => setQ(qRaw.trim().toLowerCase()), 150);
    return () => clearTimeout(id);
  }, [qRaw]);

  useEffect(() => { setLimit(PAGE); }, [q, platform, category, showDev, sort]);

  const haystack = useMemo(() => (apps ? apps.map((a) => `${a.name} ${a.owner} ${a.repo} ${a.desc}`.toLowerCase()) : []), [apps]);

  const filtered = useMemo(() => {
    if (!apps) return [];
    const out: Card[] = [];
    const terms = q ? q.split(/\s+/) : [];
    for (let i = 0; i < apps.length; i++) {
      const a = apps[i];
      const isDev = a.dev || a.category === 'developer';
      if (isDev && !showDev && category !== 'developer') continue;
      if (platform !== 'all' && !a.platforms.includes(platform)) continue;
      if (category !== 'all' && a.category !== category) continue;
      if (terms.length && !terms.every((w) => haystack[i].includes(w))) continue;
      out.push(a);
    }
    const eff: Sort = sort === 'trending' && !trendingReady ? 'latest' : sort;
    if (eff === 'popular') out.sort((a, b) => b.stars - a.stars);
    else if (eff === 'trending') {
      const ranked = out.filter((a) => a.trending?.rank != null);
      ranked.sort((a, b) => (a.trending!.rank as number) - (b.trending!.rank as number));
      return ranked;
    } else out.sort((a, b) => (b.latest_release_at || '').localeCompare(a.latest_release_at || ''));
    return out;
  }, [apps, haystack, q, platform, category, showDev, sort, trendingReady]);

  const sorts: Sort[] = trendingReady ? ['trending', 'popular', 'latest'] : ['popular', 'latest'];
  const visible = filtered.slice(0, limit);

  return (
    <>
      <section className="hero">
        <h1>{t.home.heroTitle}</h1>
        <p>{t.home.heroText}</p>
      </section>

      <div className="controls">
        <input
          className="search" type="search" value={qRaw} onChange={(e) => setQRaw(e.target.value)}
          placeholder={t.home.search} aria-label={t.home.search} data-testid="search"
        />
        <div className="chips" role="group" aria-label={t.home.platform}>
          <span className="lbl">{t.home.platform}</span>
          <button type="button" className="chip" aria-pressed={platform === 'all'} onClick={() => setPlatform('all')} data-testid="plat-all">{t.home.all}</button>
          {PLATFORMS.map((p) => (
            <button key={p} type="button" className="chip" aria-pressed={platform === p} onClick={() => setPlatform(p)} data-testid={`plat-${p}`}>{t.platforms[p]}</button>
          ))}
        </div>
        <div className="chips" role="group" aria-label={t.home.category}>
          <span className="lbl">{t.home.category}</span>
          <button type="button" className="chip" aria-pressed={category === 'all'} onClick={() => setCategory('all')}>{t.home.all}</button>
          {CATEGORIES.filter((c) => c !== 'developer').map((c) => (
            <button key={c} type="button" className="chip" aria-pressed={category === c} onClick={() => setCategory(c)} data-testid={`cat-${c}`}>{t.categories[c]}</button>
          ))}
          <button type="button" className="chip" aria-pressed={showDev} onClick={() => setShowDev((v) => !v)} data-testid="show-dev">{t.home.showDev}</button>
        </div>
        <div className="chips" role="group" aria-label={t.home.sort}>
          <span className="lbl">{t.home.sort}</span>
          {sorts.map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={(sort === 'trending' && !trendingReady ? 'latest' : sort) === s} onClick={() => setSort(s)} data-testid={`sort-${s}`}>{t.home[s]}</button>
          ))}
        </div>
      </div>

      {err && <p className="notice" role="alert">{t.ui.loadError}</p>}
      {!apps && !err && <p className="meta">{t.ui.loading}</p>}
      {apps && (
        <>
          <p className="meta" data-testid="result-count" aria-live="polite">{fill(t.home.results, { n: filtered.length })}</p>
          {filtered.length === 0 ? (
            <p className="notice" data-testid="empty">{t.home.empty}</p>
          ) : (
            <ul className="grid">
              {visible.map((a) => (
                <li key={a.slug}><AppCard app={a} /></li>
              ))}
            </ul>
          )}
          {filtered.length > limit && (
            <>
              <p className="meta" style={{ textAlign: 'center' }}>{fill(t.home.shown, { a: visible.length, b: filtered.length })}</p>
              <button type="button" className="btn more" onClick={() => setLimit((l) => l + PAGE)} data-testid="load-more">{t.home.more}</button>
            </>
          )}
        </>
      )}
    </>
  );
}
