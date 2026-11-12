'use client';

import { memo, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { AiCard } from '@/lib/ai';
import { AI_CATEGORIES, AI_TOOLS, AI_TYPES, loadAiCatalog, loadAiTrendingReady } from '@/lib/ai';
import { fill, fmtDate, fmtNum, isRising } from '@/lib/format';
import { useI18n } from './Providers';

const PAGE = 48;
type Sort = 'stars' | 'latest' | 'trending';

const AiCardView = memo(function AiCardView({ e }: { e: AiCard }) {
  const { t, lang } = useI18n();
  return (
    <Link href={`/ai/${e.slug}/`} prefetch={false} className="card" data-testid="ai-card" data-slug={e.slug}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="avatar" src={e.avatar} alt={`${e.owner} avatar`} width={48} height={48} loading="lazy" decoding="async" referrerPolicy="no-referrer" />
      <span className="card-body">
        <span className="card-title">
          <span>{e.name}</span>
          {isRising(e.trending, e.stars) && <span className="rising" data-testid="rising-badge">{t.ai.rising}</span>}
        </span>
        <span className="owner">{e.owner}</span>
        <span className="desc">{e.desc}</span>
        <span className="badges">
          {e.types.map((ty) => (
            <span key={ty} className="tbadge" data-testid="type-badge" data-type={ty}>{t.ai.types[ty] ?? ty}</span>
          ))}
          {e.tools.map((tl) => (
            <span key={tl} className="tool" data-testid="tool-badge" data-tool={tl}>{t.ai.tools[tl] ?? tl}</span>
          ))}
          <span>{'★'} {fmtNum(e.stars)}</span>
          <span>{t.ai.activity} {fmtDate(e.latest_activity_at, lang)}</span>
        </span>
      </span>
    </Link>
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
  const [docReady, setDocReady] = useState(false);

  useEffect(() => {
    loadAiCatalog().then((c) => setItems(c.entries)).catch(() => setErr(true));
    loadAiTrendingReady().then(setDocReady);
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

  const sorts: Sort[] = trendingReady ? ['trending', 'stars', 'latest'] : ['stars', 'latest'];
  const effSort: Sort = sort === 'trending' && !trendingReady ? 'stars' : sort;
  const visible = filtered.slice(0, limit);

  return (
    <>
      <section className="hero">
        <h1>{t.ai.heroTitle}</h1>
        <p>{t.ai.heroText}</p>
      </section>
      <div className="controls">
        <input className="search" type="search" value={qRaw} onChange={(e) => setQRaw(e.target.value)}
          placeholder={t.ai.search} aria-label={t.ai.search} data-testid="ai-search" />
        <div className="chips" role="group" aria-label={t.ai.type}>
          <span className="lbl">{t.ai.type}</span>
          <button type="button" className="chip" aria-pressed={type === 'all'} onClick={() => setType('all')} data-testid="type-all">{t.ai.all}</button>
          {AI_TYPES.map((x) => (
            <button key={x} type="button" className="chip" aria-pressed={type === x} onClick={() => setType(x)} data-testid={`type-${x}`}>{t.ai.types[x]}</button>
          ))}
        </div>
        <div className="chips" role="group" aria-label={t.ai.tool}>
          <span className="lbl">{t.ai.tool}</span>
          <button type="button" className="chip" aria-pressed={tool === 'all'} onClick={() => setTool('all')} data-testid="tool-all">{t.ai.all}</button>
          {AI_TOOLS.map((x) => (
            <button key={x} type="button" className="chip" aria-pressed={tool === x} onClick={() => setTool(x)} data-testid={`tool-${x}`}>{t.ai.tools[x]}</button>
          ))}
        </div>
        <div className="chips" role="group" aria-label={t.ai.category}>
          <span className="lbl">{t.ai.category}</span>
          <button type="button" className="chip" aria-pressed={category === 'all'} onClick={() => setCategory('all')} data-testid="aicat-all">{t.ai.all}</button>
          {AI_CATEGORIES.map((x) => (
            <button key={x} type="button" className="chip" aria-pressed={category === x} onClick={() => setCategory(x)} data-testid={`aicat-${x}`}>{t.ai.categories[x]}</button>
          ))}
        </div>
        <div className="chips" role="group" aria-label={t.ai.sort}>
          <span className="lbl">{t.ai.sort}</span>
          {sorts.map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={effSort === s} onClick={() => setSort(s)} data-testid={`aisort-${s}`}>{t.ai[s]}</button>
          ))}
        </div>
      </div>

      {err && <p className="notice" role="alert">{t.ui.loadError}</p>}
      {!items && !err && <p className="meta">{t.ui.loading}</p>}
      {items && (
        <>
          <p className="meta" data-testid="ai-result-count" aria-live="polite">{fill(t.ai.results, { n: filtered.length })}</p>
          {filtered.length === 0 ? (
            <p className="notice" data-testid="ai-empty">{t.ai.empty}</p>
          ) : (
            <ul className="grid">
              {visible.map((e) => <li key={e.slug}><AiCardView e={e} /></li>)}
            </ul>
          )}
          {filtered.length > limit && (
            <>
              <p className="meta" style={{ textAlign: 'center' }}>{fill(t.ai.shown, { a: visible.length, b: filtered.length })}</p>
              <button type="button" className="btn more" onClick={() => setLimit((l) => l + PAGE)} data-testid="ai-load-more">{t.ai.more}</button>
            </>
          )}
        </>
      )}
    </>
  );
}
