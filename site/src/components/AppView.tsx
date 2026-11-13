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
import { Eyebrow, Icon } from './Ui';

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

  if (err) return (<><Link href="/" className="back-link"><Icon name="arrowLeft" size={15} /> {t.app.back}</Link><p className="notice" role="alert">{t.app.notFound}</p></>);
  if (!app) return <p className="meta">{t.ui.loading}</p>;

  const trust = app.trust || {};
  const shownAssets = showAll ? sortedAssets : sortedAssets.slice(0, 30);
  const pub = rel?.published_at ? new Date(rel.published_at) : null;
  const pubOk = pub && !Number.isNaN(pub.getTime());
  const pubDay = pubOk ? String(pub.getUTCDate()).padStart(2, '0') : '';
  const pubMon = pubOk ? pub.toLocaleDateString(lang === 'en' ? 'en-US' : 'id-ID', { month: 'short', timeZone: 'UTC' }).toUpperCase() : '';
  const letter = (app.name.match(/[A-Za-z0-9]/)?.[0] || '#').toUpperCase();
  const catLabel = t.categories[app.category] || app.category;

  return (
    <>
      <Link href="/" className="back-link"><Icon name="arrowLeft" size={15} /> {t.app.back}</Link>
      <section className="app-hero">
        <div className="app-identity">
          <div className="app-glyph" aria-hidden="true"><span>{letter}</span><i /><i /><i /></div>
          <div>
            <Eyebrow>{catLabel.toUpperCase()}</Eyebrow>
            <h1 data-testid="app-name">{app.name}</h1>
            <p className="app-owner">{app.owner}</p>
          </div>
        </div>
        <p className="app-deck">{app.desc}</p>
        <div className="app-tags">
          {app.platforms.map((p) => <span key={p}>{t.platforms[p]}</span>)}
          {app.license && <span>{app.license}</span>}
        </div>
      </section>

      <section className="release-panel" aria-live="polite" data-testid="dl-box" data-os={os || ''}>
        <div className="release-side">
          <Eyebrow>{t.app.published.toUpperCase()}</Eyebrow>
          {pubOk && <span className="release-date">{pubDay} <span>{pubMon}</span><br />{pub.getUTCFullYear()}</span>}
          <span className="release-rule" />
        </div>
        <div className="release-main">
          <div className="release-main-head">
            <div><span className="release-label">{t.app.version.toUpperCase()}</span><h2>{rel?.tag || '-'}</h2></div>
            <label className="version-select-label">{t.app.version}
              <select value={rel?.tag || ''} onChange={(e) => setTag(e.target.value)} data-testid="version-select" aria-label={t.app.version}>
                {list.map((r) => <option key={r.tag} value={r.tag}>{r.tag}</option>)}
              </select>
            </label>
          </div>
          {!rel && <p className="notice">{t.app.noBuild.replace('{os}', osName)}</p>}
          {rel && known && buttons.length > 0 && (
            <>
              <div className="release-dl">
                {buttons.map((b, i) => (
                  <a
                    key={b.cell} href={b.asset.url} rel="noopener noreferrer"
                    className={i === 0 ? 'btn primary' : 'btn'} data-testid="dl-btn" data-cell={b.cell}
                  >
                    <Icon name="download" size={16} />
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
          <div className="release-tabs" role="tablist">
            <button type="button" role="tab" className={tab === 'stable' ? 'active' : ''} aria-selected={tab === 'stable'} data-testid="tab-stable" disabled={stable.length === 0}
              onClick={() => { setTab('stable'); setTag(stable[0]?.tag || ''); }}>{t.app.stable} <span>({stable.length})</span></button>
            <button type="button" role="tab" className={tab === 'pre' ? 'active' : ''} aria-selected={tab === 'pre'} data-testid="tab-pre" disabled={pre.length === 0}
              title={pre.length === 0 ? t.app.noPre : undefined}
              onClick={() => { setTab('pre'); setTag(pre[0]?.tag || ''); }}>{t.app.pre} <span>({pre.length})</span></button>
          </div>
          {rel && (
            <div className="release-asset-summary">
              <span>{t.app.assets} ({rel.assets.length})</span>
              <span>{t.app.published}: {fmtDate(rel.published_at, lang)}</span>
            </div>
          )}
        </div>
      </section>

      <div className="app-action-row">
        <button type="button" className={`save-app-button ${mine ? 'saved' : ''}`} onClick={toggleMine} data-testid="add-mine" aria-pressed={mine}>
          <Icon name={mine ? 'check' : 'sparkles'} size={15} />{mine ? t.app.inMine : t.app.addMine}
        </button>
      </div>

      <section className="stat-strip">
        <div className="section-stamp"><span>01</span><h2>{t.app.stats}</h2></div>
        <div className="stats-grid">
          <div><span>{t.app.statStars.toUpperCase()}</span><strong><Icon name="star" fill />{fmtNum(app.stars)}</strong></div>
          <div><span>{t.app.statDownloads.toUpperCase()}</span><strong><Icon name="download" />{fmtNum(app.downloads_total)}</strong></div>
          <div><span>{t.app.statForks.toUpperCase()}</span><strong><Icon name="branch" />{fmtNum(app.forks)}</strong></div>
          <div><span>{t.app.statLicense.toUpperCase()}</span><strong><Icon name="shield" />{app.license || '-'}</strong></div>
        </div>
        <div className="app-source-links">
          <a href={`https://github.com/${app.repo}`} rel="noopener noreferrer">{t.app.repo} <Icon name="external" /></a>
          {app.homepage && /^https?:\/\//i.test(app.homepage) && <a href={app.homepage} rel="noopener noreferrer nofollow">{t.app.homepage} <Icon name="external" /></a>}
        </div>
      </section>

      <section className="trust-panel" data-testid="trust">
        <div className="trust-heading"><span className="trust-icon"><Icon name="shield" /></span><div><h2>{t.app.trustTitle}</h2></div></div>
        <p className="trust-intro">{t.app.trustIntro}</p>
        <ul className="trust-list">
          <li>{trust.curated_rules ? fill(t.app.trustCurated, { rules: trust.rules || '' }) : t.app.trustNotCurated}</li>
          {typeof trust.has_checksum_asset === 'boolean' && <li>{trust.has_checksum_asset ? t.app.trustChecksumYes : t.app.trustChecksumNo}</li>}
          <li>{t.app.trustSigned}</li>
          {trust.source && <li>{t.app.trustSource}</li>}
          {trust.picker && <li>{t.app.trustPicker}</li>}
        </ul>
        <p className="trust-intro" style={{ margin: 0 }}>
          {(os === 'windows' || !known) && <><Link href="/panduan/windows/" data-testid="guide-win">{t.app.warnWindows}</Link>. </>}
          {(os === 'macos' || !known) && <><Link href="/panduan/macos/" data-testid="guide-mac">{t.app.warnMacos}</Link>.</>}
        </p>
      </section>

      {rel && (
        <div className="app-detail-grid">
          <section className="assets-panel">
            <div className="panel-heading">
              <div><h2>{t.app.assets} <span>({rel.assets.length})</span></h2></div>
            </div>
            <p className="panel-description">{t.app.assetsHint}</p>
            <div className="asset-list" data-testid="asset-list">
              {shownAssets.map((a) => (
                <div key={a.name} className={`asset-row ${known && a.os === known ? 'asset-highlight' : ''}`}>
                  <span className="asset-icon"><Icon name="file" /></span>
                  <div className="asset-info">
                    <span className="asset-platform">{a.os === 'unknown' ? t.app.unlabeled : (t.platforms[a.os] || a.os)}{a.arch && a.arch !== 'unknown' ? ` ${a.arch}` : ''}</span>
                    <a className="asset-name" href={a.url} rel="noopener noreferrer">{a.name}</a>
                    <small>{fmtSize(a.size)} <span>·</span> {fmtNum(a.downloads)} {'↓'}</small>
                  </div>
                  <a className="asset-download" href={a.url} rel="noopener noreferrer" aria-hidden="true" tabIndex={-1}><Icon name="arrowDown" /></a>
                </div>
              ))}
            </div>
            {sortedAssets.length > shownAssets.length && (
              <button type="button" className="download-all" onClick={() => setShowAll(true)}>{fill(t.app.showAll, { n: sortedAssets.length })} <Icon name="arrowRight" /></button>
            )}
          </section>
          <section className="release-notes">
            <div className="panel-heading">
              <div><h2>{t.app.notes} {rel.tag}</h2></div>
              <span className="notes-version">{rel.tag}</span>
            </div>
            <div className="notes-body">
              {rel.notes_md ? <Md text={rel.notes_md} /> : <p>{t.app.noNotes}</p>}
            </div>
            {rel.notes_md && rel.notes_md.length >= 4000 && <div className="note-callout"><Icon name="info" /><span>{t.app.notesTrunc}</span></div>}
          </section>
        </div>
      )}
    </>
  );
}
