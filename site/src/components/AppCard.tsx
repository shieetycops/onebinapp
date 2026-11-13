'use client';

import { memo, type ReactNode } from 'react';
import Link from 'next/link';
import type { Card } from '@/lib/types';
import { fmtDate, fmtNum, isRising } from '@/lib/format';
import { useI18n } from './Providers';
import { Icon, Mark } from './Ui';

/** Card with the reference markup: index + tile + kind label, copy, platforms + stars. */
export function DirCard({ href, testid, slug, index, name, kind, owner, desc, badges, bottom, stars }: {
  href: string; testid: string; slug: string; index: number; name: string; kind: string; owner: string; desc: string;
  badges?: ReactNode; bottom: ReactNode; stars: string;
}) {
  return (
    <Link href={href} prefetch={false} className={`directory-card card-${index % 4}`} data-testid={testid} data-slug={slug}>
      <div className="directory-card-top"><span className="item-index">{String(index + 1).padStart(2, '0')}</span><Mark name={name} /><span className="kind-label">{kind}</span></div>
      <div className="directory-card-copy"><h3>{name}{badges}<Icon name="arrowUpRight" /></h3><span className="owner">{owner}</span><p>{desc}</p></div>
      <div className="directory-card-bottom"><div className="platforms">{bottom}</div><span className="stars"><Icon name="star" size={13} fill /> {stars}</span></div>
    </Link>
  );
}

function AppCardInner({ app, index = 0 }: { app: Card; index?: number }) {
  const { t, lang } = useI18n();
  return (
    <DirCard
      href={`/app/${app.slug}/`} testid="app-card" slug={app.slug} index={index} name={app.name}
      kind={t.categories[app.category] || app.category}
      owner={`${app.owner} · ${t.home.released} ${fmtDate(app.latest_release_at, lang)}`}
      desc={app.desc} stars={fmtNum(app.stars)}
      badges={<>
        {app.is_new && <span className="badge-new">{t.home.newBadge}</span>}
        {isRising(app.trending, app.stars) && <span className="badge-rising" data-testid="rising-badge">{t.home.rising}</span>}
      </>}
      bottom={app.platforms.map((p) => <span key={p} data-os={p}>{t.platforms[p]}</span>)}
    />
  );
}

export const AppCard = memo(AppCardInner);
