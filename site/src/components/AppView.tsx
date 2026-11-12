'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import type { AppDetail, Asset, OS, Release, VisitorOS } from '@/lib/types';
import { loadApp } from '@/lib/data';
import { detectOS } from '@/lib/os';
import { fill, fmtDate, fmtNum, fmtSize } from '@/lib/format';
import { readMine, writeMine } from '@/lib/store';
import { useI18n } from './Providers';

interface Btn { cell: string; asset: Asset; archLabel: string | null }

const CELLS: Record<OS, [string, string][]> = {
  windows: [['windows-x64', 'x64'], ['windows-arm64', 'ARM64']],
  macos: [['macos-arm64', 'apple'], ['macos-x64', 'intel']],
  linux: [['linux-x64', 'x64'], ['linux-arm64', 'ARM64']],
  android: [['android', '']],
};

function buildButtons(os: OS, rel: Release, archName: (k: string) => string): Btn[] {
  const found: { cell: string; asset: Asset; key: string }[] = [];
  for (const [cell, key] of CELLS[os]) {
    const name = rel.picks?.[cell];
    if (!name) continue;
    const asset = rel.assets.find((a) => a.name === name);
    if (!asset) continue; // unresolved pick counts as silent
    found.push({ cell, asset, key });
  }
  // Same asset for several cells (e.g. universal macOS dmg): one button, no arch claim.
  const uniq: typeof found = [];
  for (const f of found) if (!uniq.some((u) => u.asset.name === f.asset.name)) uniq.push(f);
  if (uniq.length === 1 && (found.length > 1 || os === 'android' || uniq[0].key === 'x64')) {
    return [{ cell: uniq[0].cell, asset: uniq[0].asset, archLabel: null }];
  }
  return uniq.map((u) => ({ cell: u.cell, asset: u.asset, archLabel: archName(u.key) }));
}

function Md({ text }: { text: string }) {
  return (
    <div className="md" data-testid="release-notes">
      <ReactMarkdown
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer nofollow ugc">{children}</a>
          ),
          img: ({ src, alt }) => (typeof src === 'string' && src ? <a href={src} target="_blank" rel="noopener noreferrer nofollow ugc">{alt || src}</a> : <span>{alt}</span>),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

export default function AppView({ slug }: { slug: string }) {
  const { t, lang } = useI18n();
  const [app, setApp] = useState<AppDetail | null>(null);
  const [err, setErr] = useState(false);
  const [os, setOs] = useState<VisitorOS | null>(null);
  const [tab, setTab] = useState<'stable' | 'pre'>('stable');
  const [tag, setTag] = useState<string>('');
  const [showAll, setShowAll] = useState(false);
  const [mine, setMine] = useState(false);

  useEffect(() => {
    setOs(detectOS());
    setMine(readMine().includes(slug));
    loadApp(slug)
      .then((a) => {
        const releases = [...a.releases].sort((x, y) => (y.published_at || '').localeCompare(x.published_at || ''));
        a.releases = releases;
        const def = releases.find((r) => r.tag === a.version) || releases.find((r) => !r.prerelease) || releases[0];
        setApp(a);
        if (def) { setTab(def.prerelease ? 'pre' : 'stable'); setTag(def.tag); }
      })
      .catch(() => setErr(true));
  }, [slug]);

  const stable = useMemo(() => (app ? app.releases.filter((r) => !r.prerelease) : []), [app]);
  const pre = useMemo(() => (app ? app.releases.filter((r) => r.prerelease) : []), [app]);
  const list = tab === 'stable' ? stable : pre;
  const rel = list.find((r) => r.tag === tag) || list[0] || null;

  const archName = (k: string) => (k === 'apple' ? t.app.appleSilicon : k === 'intel' ? t.app.intel : k);
  const osName = os ? t.platforms[os] : '';
  const known: OS | null = os === 'windows' || os === 'macos' || os === 'linux' || os === 'android' ? os : null;

  const buttons = useMemo(() => (rel && known ? buildButtons(known, rel, archName) : []), [rel, known, lang]); // eslint-disable-line react-hooks/exhaustive-deps
  const osAssets = rel && known ? rel.assets.filter((a) => a.os === known) : [];

  const sortedAssets = useMemo(() => {
    if (!rel) return [];
    const mineFirst = (a: Asset) => (known && a.os === known ? 0 : 1);
    return [...rel.assets].sort((a, b) => mineFirst(a) - mineFirst(b));
  }, [rel, known]);

  function toggleMine() {
    const cur = readMine();
    const next = cur.includes(slug) ? cur.filter((s) => s !== slug) : [...cur, slug];
    writeMine(next);
    setMine(next.includes(slug));
  }

  if (err) return (<><Link href="/" className="crumb">{t.app.back}</Link><p className="notice" role="alert">{t.app.notFound}</p></>);
  if (!app) return <p className="meta">{t.ui.loading}</p>;

  const trust = app.trust || {};
  const shownAssets = showAll ? sortedAssets : sortedAssets.slice(0, 30);

  return (
    <article>
      <Link href="/" className="crumb">&larr; {t.app.back}</Link>
      <div className="app-head">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="avatar" src={app.avatar} alt={`${app.owner} avatar`} width={64} height={64} loading="lazy" referrerPolicy="no-referrer" />
        <div>
          <h1 data-testid="app-name">{app.name}</h1>
          <div className="owner">{app.owner} &middot; {t.categories[app.category] || app.category}</div>
        </div>
      </div>
      <p>{app.desc}</p>
      <div className="badges" style={{ marginBottom: 8 }}>
        {app.platforms.map((p) => <span key={p} className="os">{t.platforms[p]}</span>)}
      </div>

      <section className="dl-box" aria-live="polite" data-testid="dl-box" data-os={os || ''}>
        {!rel && <p className="notice">{t.app.noBuild.replace('{os}', osName)}</p>}
        {rel && known && buttons.length > 0 && (
          <>
            <div className="dl-actions">
              {buttons.map((b, i) => (
                <a
                  key={b.cell} href={b.asset.url} rel="noopener noreferrer"
                  className={i === 0 ? 'btn primary' : 'btn'} data-testid="dl-btn" data-cell={b.cell}
                >
                  {b.archLabel ? fill(t.app.downloadArch, { os: osName, arch: b.archLabel }) : fill(t.app.downloadFor, { os: osName })}
                </a>
              ))}
            </div>
            <p className="note">
              {known === 'macos' && buttons.length > 0 && buttons[0].archLabel ? t.app.macNote + ' ' : ''}
              {known !== 'macos' && buttons.length > 1 ? t.app.archNote + ' ' : ''}
              {t.app.pickedBy} ({rel.tag}, {buttons.map((b) => b.asset.name).join(', ')})
            </p>
          </>
        )}
        {rel && known && buttons.length === 0 && osAssets.length > 0 && (
          <p className="notice" data-testid="dl-silent">{fill(t.app.pickerSilent, { os: osName })}</p>
        )}
        {rel && known && buttons.length === 0 && osAssets.length === 0 && (
          <p className="notice" data-testid="dl-nobuild">{fill(t.app.noBuild, { os: osName })}</p>
        )}
        {rel && !known && os && <p className="notice" data-testid="dl-unknown">{t.app.unknownOs}</p>}
        <div className="tabs" role="tablist">
          <button type="button" role="tab" className="tab" aria-selected={tab === 'stable'} data-testid="tab-stable" disabled={stable.length === 0}
            onClick={() => { setTab('stable'); setTag(stable[0]?.tag || ''); }}>{t.app.stable} ({stable.length})</button>
          <button type="button" role="tab" className="tab" aria-selected={tab === 'pre'} data-testid="tab-pre" disabled={pre.length === 0}
            title={pre.length === 0 ? t.app.noPre : undefined}
            onClick={() => { setTab('pre'); setTag(pre[0]?.tag || ''); }}>{t.app.pre} ({pre.length})</button>
          <label className="owner" style={{ marginLeft: 'auto' }}>
            {t.app.version}{' '}
            <select value={rel?.tag || ''} onChange={(e) => setTag(e.target.value)} data-testid="version-select" aria-label={t.app.version}>
              {list.map((r) => <option key={r.tag} value={r.tag}>{r.tag}</option>)}
            </select>
          </label>
        </div>
        {rel && <p className="note">{t.app.published}: {fmtDate(rel.published_at, lang)}</p>}
      </section>

      <div className="panel">
        <button type="button" className="btn" onClick={toggleMine} data-testid="add-mine" aria-pressed={mine}>
          {mine ? t.app.inMine : t.app.addMine}
        </button>
      </div>

      <section className="panel">
        <h2>{t.app.stats}</h2>
        <dl className="stats">
          <div><dt>{t.app.statStars}</dt><dd>{fmtNum(app.stars)}</dd></div>
          <div><dt>{t.app.statDownloads}</dt><dd>{fmtNum(app.downloads_total)}</dd></div>
          <div><dt>{t.app.statForks}</dt><dd>{fmtNum(app.forks)}</dd></div>
          <div><dt>{t.app.statLicense}</dt><dd>{app.license || '-'}</dd></div>
        </dl>
        <p className="note" style={{ marginTop: 10 }}>
          <a href={`https://github.com/${app.repo}`} rel="noopener noreferrer">{t.app.repo}</a>
          {app.homepage && /^https?:\/\//i.test(app.homepage) && <> &middot; <a href={app.homepage} rel="noopener noreferrer nofollow">{t.app.homepage}</a></>}
        </p>
      </section>

      <section className="panel" data-testid="trust">
        <h2>{t.app.trustTitle}</h2>
        <p className="note">{t.app.trustIntro}</p>
        <ul className="trust">
          <li>{trust.curated_rules ? fill(t.app.trustCurated, { rules: trust.rules || '' }) : t.app.trustNotCurated}</li>
          {typeof trust.has_checksum_asset === 'boolean' && <li>{trust.has_checksum_asset ? t.app.trustChecksumYes : t.app.trustChecksumNo}</li>}
          <li>{t.app.trustSigned}</li>
          {trust.source && <li>{t.app.trustSource}</li>}
          {trust.picker && <li>{t.app.trustPicker}</li>}
        </ul>
        <p className="note">
          {(os === 'windows' || !known) && <><Link href="/panduan/windows/" data-testid="guide-win">{t.app.warnWindows}</Link>. </>}
          {(os === 'macos' || !known) && <><Link href="/panduan/macos/" data-testid="guide-mac">{t.app.warnMacos}</Link>.</>}
        </p>
      </section>

      {rel && (
        <section className="panel">
          <h2>{t.app.assets} ({rel.assets.length})</h2>
          <p className="note">{t.app.assetsHint}</p>
          <ul className="assets" data-testid="asset-list">
            {shownAssets.map((a) => (
              <li key={a.name} className={known && a.os === known ? 'mine' : ''}>
                <span className="os">{a.os === 'unknown' ? t.app.unlabeled : (t.platforms[a.os] || a.os)}{a.arch && a.arch !== 'unknown' ? ` ${a.arch}` : ''}</span>
                <a href={a.url} rel="noopener noreferrer">{a.name}</a>
                <span className="sub">{fmtSize(a.size)} &middot; {fmtNum(a.downloads)} {'↓'}</span>
              </li>
            ))}
          </ul>
          {sortedAssets.length > shownAssets.length && (
            <button type="button" className="btn" style={{ marginTop: 8 }} onClick={() => setShowAll(true)}>{fill(t.app.showAll, { n: sortedAssets.length })}</button>
          )}
        </section>
      )}

      {rel && (
        <section className="panel">
          <h2>{t.app.notes} {rel.tag}</h2>
          {rel.notes_md ? <Md text={rel.notes_md} /> : <p className="note">{t.app.noNotes}</p>}
          {rel.notes_md && rel.notes_md.length >= 4000 && <p className="note">{t.app.notesTrunc}</p>}
        </section>
      )}
    </article>
  );
}
