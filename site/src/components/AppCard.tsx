'use client';

import { memo } from 'react';
import Link from 'next/link';
import type { Card } from '@/lib/types';
import { fmtDate, fmtNum, isRising } from '@/lib/format';
import { useI18n } from './Providers';

function AppCardInner({ app }: { app: Card }) {
  const { t, lang } = useI18n();
  return (
    <Link href={`/app/${app.slug}/`} prefetch={false} className="card" data-testid="app-card" data-slug={app.slug}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="avatar" src={app.avatar} alt={`${app.owner} avatar`} width={48} height={48} loading="lazy" decoding="async" referrerPolicy="no-referrer" />
      <span className="card-body">
        <span className="card-title">
          <span>{app.name}</span>
          {app.is_new && <span className="new">{t.home.newBadge}</span>}
          {isRising(app.trending, app.stars) && <span className="rising" data-testid="rising-badge">{t.home.rising}</span>}
        </span>
        <span className="owner">{app.owner}</span>
        <span className="desc">{app.desc}</span>
        <span className="badges">
          {app.platforms.map((p) => (
            <span key={p} className="os" data-os={p}>{t.platforms[p]}</span>
          ))}
          <span>{'★'} {fmtNum(app.stars)}</span>
          <span>{t.home.released} {fmtDate(app.latest_release_at, lang)}</span>
        </span>
      </span>
    </Link>
  );
}

export const AppCard = memo(AppCardInner);
