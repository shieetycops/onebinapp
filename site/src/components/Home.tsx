'use client';

import { useEffect, useMemo, useState } from 'react';
import type { Card, OS, Trending } from '@/lib/types';
import { CATEGORIES, PLATFORMS } from '@/lib/types';
import { loadCatalog, loadTrendingDoc, loadTrendingReady } from '@/lib/data';
import { fill } from '@/lib/format';
import { AppCard } from './AppCard';
import { TopDaily, type TopItem } from './TopDaily';
import { useI18n } from './Providers';
import { DirectoryIntro, FilterToggle, Hero, Icon, Manifesto, SearchField } from './Ui';

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
  const [showFilters, setShowFilters] = useState(true);
  const [doc, setDoc] = useState<Trending | null>(null);

  useEffect(() => {
    loadCatalog().then((c) => setApps(c.apps)).catch(() => setErr(true));
    loadTrendingReady().then(setTrendingReady);
    loadTrendingDoc('trending').then(setDoc);
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

  const top = useMemo<TopItem[]>(() => {
    if (!apps || !doc?.daily?.ready) return [];
    const by = new Map(apps.map((a) => [a.slug, a]));
    const out: TopItem[] = [];
    for (const it of doc.daily.items) {
      const a = by.get(it.slug);
      if (!a || a.dev || a.category === 'developer') continue;
      out.push({ slug: a.slug, href: `/app/${a.slug}/`, name: a.name, owner: a.owner, d1: it.d1, stars: a.stars });
      if (out.length === 10) break;
    }
    return out;
  }, [apps, doc]);

  const sorts: Sort[] = trendingReady ? ['trending', 'popular', 'latest'] : ['popular', 'latest'];
  const visible = filtered.slice(0, limit);

  const effSort: Sort = sort === 'trending' && !trendingReady ? 'latest' : sort;
  const activeFilters = (platform !== 'all' ? 1 : 0) + (category !== 'all' ? 1 : 0) + (showDev ? 1 : 0);
  const reset = () => { setQRaw(''); setPlatform('all'); setCategory('all'); setShowDev(false); };

  return (
    <>
      <Hero
        kicker={t.chrome.kickerApp} count={apps ? fill(t.chrome.count, { n: apps.length }) : null}
        title={t.home.heroTitle} text={t.home.heroText} rail={t.chrome.railApp} ticker={t.chrome.ticker}
        jump={t.chrome.jump} target="#directory" sticker={t.chrome.stickerApp as [string, string]} stickerNote={t.chrome.stickerNoteApp as [string, string]}
      />
      <TopDaily items={top} baseline={doc?.daily?.baseline ?? null} />
      <section id="directory" className="directory-section">
        <DirectoryIntro index={t.chrome.introIndex} label={t.chrome.introLabel} a={t.chrome.introA} b={t.chrome.introB} desc={t.chrome.introDescApp} />
        <div className="discovery-bar">
          <SearchField>
            <input type="search" value={qRaw} onChange={(e) => setQRaw(e.target.value)} placeholder={t.home.search} aria-label={t.home.search} data-testid="search" />
          </SearchField>
          <FilterToggle open={showFilters} count={activeFilters} label={t.chrome.filters} onClick={() => setShowFilters((v) => !v)} />
        </div>
        {showFilters && (
          <div className="filter-drawer">
            <div className="filter-group" role="group" aria-label={t.home.platform}>
              <span>{t.home.platform.toUpperCase()}</span>
              <div className="filter-pills">
                <button type="button" aria-pressed={platform === 'all'} onClick={() => setPlatform('all')} data-testid="plat-all">{t.home.all}</button>
                {PLATFORMS.map((p) => (
                  <button key={p} type="button" aria-pressed={platform === p} onClick={() => setPlatform(p)} data-testid={`plat-${p}`}>{t.platforms[p]}</button>
                ))}
              </div>
            </div>
            <div className="filter-group" role="group" aria-label={t.home.category}>
              <span>{t.home.category.toUpperCase()}</span>
              <div className="filter-pills">
                <button type="button" aria-pressed={category === 'all'} onClick={() => setCategory('all')}>{t.home.all}</button>
                {CATEGORIES.filter((c) => c !== 'developer').map((c) => (
                  <button key={c} type="button" aria-pressed={category === c} onClick={() => setCategory(c)} data-testid={`cat-${c}`}>{t.categories[c]}</button>
                ))}
                <button type="button" aria-pressed={showDev} onClick={() => setShowDev((v) => !v)} data-testid="show-dev">{t.home.showDev}</button>
              </div>
            </div>
            <div className="filter-group" role="group" aria-label={t.home.sort}>
              <span>{t.home.sort.toUpperCase()}</span>
              <div className="filter-pills">
                {sorts.map((s) => (
                  <button key={s} type="button" aria-pressed={effSort === s} onClick={() => setSort(s)} data-testid={`sort-${s}`}>{t.home[s]}</button>
                ))}
              </div>
            </div>
          </div>
        )}

        {err && <p className="notice" role="alert">{t.ui.loadError}</p>}
        {!apps && !err && <div className="listing-heading"><span>{t.ui.loading}</span></div>}
        {apps && (
          <>
            <div className="listing-heading">
              <span className="listing-count" data-testid="result-count" aria-live="polite">{fill(t.home.results, { n: filtered.length })}</span>
              <span className="listing-sort">{t.home.sort} <b>{t.home[effSort]} ↓</b></span>
            </div>
            {filtered.length === 0 ? (
              <div className="no-results">
                <Icon name="search" />
                <p data-testid="empty">{t.home.empty}</p>
                <button type="button" onClick={reset}>{t.chrome.clear} <Icon name="x" /></button>
              </div>
            ) : (
              <div className="directory-grid">
                {visible.map((a, i) => <AppCard key={a.slug} app={a} index={i} />)}
              </div>
            )}
            {filtered.length > limit && (
              <>
                <p className="shown-note">{fill(t.home.shown, { a: visible.length, b: filtered.length })}</p>
                <button type="button" className="more-button" onClick={() => setLimit((l) => l + PAGE)} data-testid="load-more">{t.home.more} <Icon name="arrowRight" /></button>
              </>
            )}
          </>
        )}
      </section>
      <Manifesto top={t.chrome.manTop} a={t.chrome.manA} b={t.chrome.manB} link={t.chrome.manLink} target="#directory" />
    </>
  );
}
