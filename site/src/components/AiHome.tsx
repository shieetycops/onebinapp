'use client';

import { memo, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { AiCard } from '@/lib/ai';
import { AI_CATEGORIES, AI_TOOLS, AI_TYPES, loadAiCatalog, loadAiTrendingReady } from '@/lib/ai';
import { loadTrendingDoc } from '@/lib/data';
import type { Trending } from '@/lib/types';
import { TopDaily, type TopItem } from './TopDaily';
import { fill, fmtDate, fmtNum, isRising } from '@/lib/format';
import { useI18n } from './Providers';
import { DirectoryIntro, FilterToggle, Hero, Icon, Manifesto, SearchField } from './Ui';
import { DirCard } from './AppCard';

const PAGE = 48;
type Sort = 'stars' | 'latest' | 'trending';

const AiCardView = memo(function AiCardView({ e, index }: { e: AiCard; index: number }) {
  const { t, lang } = useI18n();
  return (
    <DirCard
      href={`/ai/${e.slug}/`} testid="ai-card" slug={e.slug} index={index} name={e.name}
      kind={t.ai.types[e.types[0]] ?? e.types[0] ?? ''}
      owner={`${e.owner} · ${t.ai.activity} ${fmtDate(e.latest_activity_at, lang)}`}
      desc={e.desc} stars={fmtNum(e.stars)}
      badges={isRising(e.trending, e.stars) ? <span className="badge-rising" data-testid="rising-badge">{t.ai.rising}</span> : null}
      bottom={<>
        {e.types.map((ty) => <span key={ty} className="tbadge" data-testid="type-badge" data-type={ty}>{t.ai.types[ty] ?? ty}</span>)}
        {e.tools.map((tl) => <span key={tl} className="tool" data-testid="tool-badge" data-tool={tl}>{t.ai.tools[tl] ?? tl}</span>)}
      </>}
    />
  );
});

export default function AiHome() {
  const { t } = useI18n();
  const [items, setItems] = useState<AiCard[] | null>(null);
  const [err, setErr] = useState(false);
  const [qRaw, setQRaw] = useState('');
  const [q, setQ] = useState('');
  const [type, setType] = useState<string>('all');
  const [tool, setTool] = useState<string>('all');
  const [category, setCategory] = useState<string>('all');
  const [sort, setSort] = useState<Sort>('stars');
  const [limit, setLimit] = useState(PAGE);
  const [showFilters, setShowFilters] = useState(true);
  const [doc, setDoc] = useState<Trending | null>(null);
  const [docReady, setDocReady] = useState(false);

  useEffect(() => {
    loadAiCatalog().then((c) => setItems(c.entries)).catch(() => setErr(true));
    loadAiTrendingReady().then(setDocReady);
    loadTrendingDoc('trending-ai').then(setDoc);
  }, []);
  useEffect(() => {
    const id = setTimeout(() => setQ(qRaw.trim().toLowerCase()), 150);
    return () => clearTimeout(id);
  }, [qRaw]);
  useEffect(() => { setLimit(PAGE); }, [q, type, tool, category, sort]);

  // section-specific: trending-ai.json says ready (builder also stamps ready on every card)
  const trendingReady = docReady || (!!items && items.some((e) => e.trending && e.trending.ready === true));
  const hay = useMemo(() => (items ? items.map((e) => `${e.name} ${e.owner} ${e.repo} ${e.desc}`.toLowerCase()) : []), [items]);

  const filtered = useMemo(() => {
    if (!items) return [];
    const terms = q ? q.split(/\s+/) : [];
    const out: AiCard[] = [];
    items.forEach((e, i) => {
      if (type !== 'all' && !e.types.includes(type)) return;
      if (tool !== 'all' && !e.tools.includes(tool)) return;
      if (category !== 'all' && e.category !== category) return;
      if (terms.length && !terms.every((w) => hay[i].includes(w))) return;
      out.push(e);
    });
    const eff: Sort = sort === 'trending' && !trendingReady ? 'stars' : sort;
    if (eff === 'stars') out.sort((a, b) => b.stars - a.stars);
    else if (eff === 'latest') out.sort((a, b) => (b.latest_activity_at || '').localeCompare(a.latest_activity_at || ''));
    else {
      const ranked = out.filter((e) => e.trending?.rank != null);
      ranked.sort((a, b) => (a.trending.rank as number) - (b.trending.rank as number));
      return ranked;
    }
    return out;
  }, [items, hay, q, type, tool, category, sort, trendingReady]);

  const top = useMemo<TopItem[]>(() => {
    if (!items || !doc?.daily?.ready) return [];
    const by = new Map(items.map((e) => [e.slug, e]));
    const out: TopItem[] = [];
    for (const it of doc.daily.items) {
      const e = by.get(it.slug);
      if (!e) continue;
      out.push({ slug: e.slug, href: `/ai/${e.slug}/`, name: e.name, owner: e.owner, d1: it.d1, stars: e.stars });
      if (out.length === 10) break;
    }
    return out;
  }, [items, doc]);

  const sorts: Sort[] = trendingReady ? ['trending', 'stars', 'latest'] : ['stars', 'latest'];
  const effSort: Sort = sort === 'trending' && !trendingReady ? 'stars' : sort;
  const visible = filtered.slice(0, limit);

  const activeFilters = (type !== 'all' ? 1 : 0) + (tool !== 'all' ? 1 : 0) + (category !== 'all' ? 1 : 0);
  const reset = () => { setQRaw(''); setType('all'); setTool('all'); setCategory('all'); };

  return (
    <>
      <Hero
        kicker={t.chrome.kickerAi} count={items ? fill(t.chrome.count, { n: items.length }) : null}
        title={t.ai.heroTitle} text={t.ai.heroText} rail={t.chrome.railAi} ticker={t.chrome.ticker}
        jump={t.chrome.jump} target="#directory" sticker={t.chrome.stickerAi as [string, string]} stickerNote={t.chrome.stickerNoteAi as [string, string]}
      />
      <TopDaily items={top} baseline={doc?.daily?.baseline ?? null} ai />
      <section id="directory" className="directory-section">
        <DirectoryIntro index={t.chrome.introIndex} label={t.chrome.introLabel} a={t.chrome.introA} b={t.chrome.introB} desc={t.chrome.introDescAi} />
        <div className="discovery-bar">
          <SearchField>
            <input type="search" value={qRaw} onChange={(e) => setQRaw(e.target.value)} placeholder={t.ai.search} aria-label={t.ai.search} data-testid="ai-search" />
          </SearchField>
          <FilterToggle open={showFilters} count={activeFilters} label={t.chrome.filters} onClick={() => setShowFilters((v) => !v)} />
        </div>
        {showFilters && (
          <div className="filter-drawer">
            <div className="filter-group" role="group" aria-label={t.ai.type}>
              <span>{t.ai.type.toUpperCase()}</span>
              <div className="filter-pills">
                <button type="button" aria-pressed={type === 'all'} onClick={() => setType('all')} data-testid="type-all">{t.ai.all}</button>
                {AI_TYPES.map((x) => <button key={x} type="button" aria-pressed={type === x} onClick={() => setType(x)} data-testid={`type-${x}`}>{t.ai.types[x]}</button>)}
              </div>
            </div>
            <div className="filter-group" role="group" aria-label={t.ai.tool}>
              <span>{t.ai.tool.toUpperCase()}</span>
              <div className="filter-pills">
                <button type="button" aria-pressed={tool === 'all'} onClick={() => setTool('all')} data-testid="tool-all">{t.ai.all}</button>
                {AI_TOOLS.map((x) => <button key={x} type="button" aria-pressed={tool === x} onClick={() => setTool(x)} data-testid={`tool-${x}`}>{t.ai.tools[x]}</button>)}
              </div>
            </div>
            <div className="filter-group" role="group" aria-label={t.ai.category}>
              <span>{t.ai.category.toUpperCase()}</span>
              <div className="filter-pills">
                <button type="button" aria-pressed={category === 'all'} onClick={() => setCategory('all')} data-testid="aicat-all">{t.ai.all}</button>
                {AI_CATEGORIES.map((x) => <button key={x} type="button" aria-pressed={category === x} onClick={() => setCategory(x)} data-testid={`aicat-${x}`}>{t.ai.categories[x]}</button>)}
              </div>
            </div>
            <div className="filter-group" role="group" aria-label={t.ai.sort}>
              <span>{t.ai.sort.toUpperCase()}</span>
              <div className="filter-pills">
                {sorts.map((s) => <button key={s} type="button" aria-pressed={effSort === s} onClick={() => setSort(s)} data-testid={`aisort-${s}`}>{t.ai[s]}</button>)}
              </div>
            </div>
          </div>
        )}

        {err && <p className="notice" role="alert">{t.ui.loadError}</p>}
        {!items && !err && <div className="listing-heading"><span>{t.ui.loading}</span></div>}
        {items && (
          <>
            <div className="listing-heading">
              <span className="listing-count" data-testid="ai-result-count" aria-live="polite">{fill(t.ai.results, { n: filtered.length })}</span>
              <span className="listing-sort">{t.ai.sort} <b>{t.ai[effSort]} ↓</b></span>
            </div>
            {filtered.length === 0 ? (
              <div className="no-results">
                <Icon name="search" />
                <p data-testid="ai-empty">{t.ai.empty}</p>
                <button type="button" onClick={reset}>{t.chrome.clear} <Icon name="x" /></button>
              </div>
            ) : (
              <div className="directory-grid">
                {visible.map((e, i) => <AiCardView key={e.slug} e={e} index={i} />)}
              </div>
            )}
            {filtered.length > limit && (
              <>
                <p className="shown-note">{fill(t.ai.shown, { a: visible.length, b: filtered.length })}</p>
                <button type="button" className="more-button" onClick={() => setLimit((l) => l + PAGE)} data-testid="ai-load-more">{t.ai.more} <Icon name="arrowRight" /></button>
              </>
            )}
          </>
        )}
      </section>
      <Manifesto top={t.chrome.manTop} a={t.chrome.manA} b={t.chrome.manB} link={t.chrome.manLink} target="#directory" />
    </>
  );
}
