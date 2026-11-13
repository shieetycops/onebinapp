'use client';

import Link from 'next/link';
import { fill, fmtDay, fmtNum } from '@/lib/format';
import { useI18n } from './Providers';
import { Icon, Mark } from './Ui';

export interface TopItem { slug: string; href: string; name: string; owner: string; d1: number; stars: number }

/** "Top 10 today": the ten biggest one-day star gainers of a section. Rendered only when real daily data exists. */
export function TopDaily({ items, baseline, ai }: { items: TopItem[]; baseline: string | null; ai?: boolean }) {
  const { t, lang } = useI18n();
  const c = t.chrome;
  if (items.length === 0) return null;
  const since = fmtDay(baseline, lang);
  return (
    <section className="top-daily" data-testid="top-daily" aria-labelledby="top-daily-title">
      <div className="directory-intro">
        <div>
          <div className="section-index">{c.topIndex} <span>— {c.topLabel.toUpperCase()}</span></div>
          <h2 id="top-daily-title">{c.topA}<br /><span>{c.topB}</span></h2>
        </div>
        <p className="directory-desc">{ai ? c.topDescAi : c.topDescApp}{since && <><br /><span className="top-since">{fill(c.topSince, { date: since })}</span></>}</p>
      </div>
      <ol className="top-list">
        {items.map((it, i) => (
          <li key={it.slug}>
            <Link href={it.href} prefetch={false} className="top-row" data-testid="top-row" data-slug={it.slug}>
              <span className="top-rank">{String(i + 1).padStart(2, '0')}</span>
              <Mark name={it.name} />
              <span className="top-name"><strong>{it.name}</strong><span className="owner">{it.owner}</span></span>
              <span className="top-gain" data-testid="top-gain"><Icon name="star" size={12} fill />+{fmtNum(it.d1)}<small>{c.topStars}</small></span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
