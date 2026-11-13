'use client';

import { Fragment, useEffect, useRef, type ReactNode } from 'react';

/* Inline lucide-style icons (no icon dependency). */
const PATHS: Record<string, ReactNode> = {
  arrowUpRight: <><path d="M7 7h10v10" /><path d="M7 17 17 7" /></>,
  arrowDownRight: <><path d="m7 7 10 10" /><path d="M17 7v10H7" /></>,
  arrowRight: <><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></>,
  arrowLeft: <><path d="m12 19-7-7 7-7" /><path d="M19 12H5" /></>,
  arrowDown: <><path d="M12 5v14" /><path d="m19 12-7 7-7-7" /></>,
  search: <><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></>,
  x: <><path d="M18 6 6 18" /><path d="m6 6 12 12" /></>,
  star: <path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z" />,
  moon: <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.93 4.93 1.41 1.41" /><path d="m17.66 17.66 1.41 1.41" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m6.34 17.66-1.41 1.41" /><path d="m19.07 4.93-1.41 1.41" /></>,
  sliders: <><path d="M10 5H3" /><path d="M12 19H3" /><path d="M14 3v4" /><path d="M16 17v4" /><path d="M21 12h-9" /><path d="M21 19h-5" /><path d="M21 5h-7" /><path d="M8 10v4" /><path d="M8 12H3" /></>,
  command: <path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3" />,
  blocks: <><path d="M10 22V7a1 1 0 0 0-1-1H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5a1 1 0 0 0-1-1H2" /><rect x="14" y="2" width="8" height="8" rx="1" /></>,
  download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5" /><path d="M12 15V3" /></>,
  external: <><path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /></>,
  info: <><circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" /></>,
  shield: <><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" /><path d="m9 12 2 2 4-4" /></>,
  check: <path d="M20 6 9 17l-5-5" />,
  file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></>,
  sparkles: <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />,
  branch: <><path d="M6 3v12" /><circle cx="18" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><path d="M18 9a9 9 0 0 1-9 9" /></>,
  clipboard: <><rect x="8" y="2" width="8" height="4" rx="1" /><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" /></>,
};
export type IconName = keyof typeof PATHS;

export function Icon({ name, size, fill, className }: { name: IconName; size?: number; fill?: boolean; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width={size ?? 24} height={size ?? 24} fill={fill ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" className={className}>
      {PATHS[name]}
    </svg>
  );
}

export function Wordmark({ brand, href, label }: { brand: string; href: string; label?: string }) {
  return (
    <a className="wordmark" href={href} aria-label={label}>
      <span className="wordmark-symbol"><Icon name="blocks" /></span>
      <span>{brand}<span className="wordmark-period">.</span></span>
    </a>
  );
}

/** Search field exactly like the reference: icon, input, "/" key hint (pressing / focuses it). */
export function SearchField({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLLabelElement>(null);
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.key !== '/' || (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      e.preventDefault();
      ref.current?.querySelector('input')?.focus();
    };
    window.addEventListener('keydown', on);
    return () => window.removeEventListener('keydown', on);
  }, []);
  return (<label className="search-field" ref={ref}><Icon name="search" />{children}<kbd>/</kbd></label>);
}

function splitTitle(title: string): [string, string] {
  const i = title.indexOf(',');
  if (i > 0) return [title.slice(0, i + 1), title.slice(i + 1).trim()];
  const w = title.split(' ');
  const mid = Math.ceil(w.length / 2);
  return [w.slice(0, mid).join(' '), w.slice(mid).join(' ')];
}

/** Hero + ticker, same structure as the reference. The title is the page's only h1. */
export function Hero({ kicker, count, title, text, rail, ticker, jump, target, sticker, stickerNote }: {
  kicker: string; count: string | null; title: string; text: string; rail: string[]; ticker: string[]; jump: string; target: string;
  sticker: [string, string]; stickerNote: [string, string];
}) {
  const [a, b] = splitTitle(title);
  const run = [...ticker, ...ticker];
  return (
    <>
      <section className="hero-block">
        <div className="hero-content">
          <div className="hero-kicker"><span className="live-dot" /> {kicker.toUpperCase()}{count && <> <span className="kicker-divider">/</span> {count.toUpperCase()}</>}</div>
          <h1>{a}{' '}<br /><span>{b}</span></h1>
          <div className="hero-bottom">
            <p>{text}</p>
            <a className="round-link" href={target} aria-label={jump}><Icon name="arrowDownRight" /></a>
          </div>
        </div>
        <div className="hero-sticker" aria-hidden="true"><span className="sticker-orbit" /><span className="sticker-core">{sticker[0]}<br />{sticker[1]}</span><span className="sticker-note">{stickerNote[0]}<br />{stickerNote[1]} ↘</span></div>
        <div className="hero-rail" aria-hidden="true">{rail.map((r) => <span key={r}>{r.toUpperCase()}</span>)}</div>
      </section>
      <div className="ticker" aria-hidden="true">
        <div className="ticker-track">{[...run, ...run].map((x, i) => <Fragment key={i}>{x.toUpperCase()} <span>✳</span> </Fragment>)}</div>
      </div>
    </>
  );
}

export function DirectoryIntro({ index, label, a, b, desc }: { index: string; label: string; a: string; b: string; desc: string }) {
  return (
    <div className="directory-intro">
      <div>
        <div className="section-index">{index} <span>— {label.toUpperCase()}</span></div>
        <h2>{a}<br /><span>{b}</span></h2>
      </div>
      <p className="directory-desc">{desc}</p>
    </div>
  );
}

export function Manifesto({ top, a, b, link, target }: { top: string; a: string; b: string; link: string; target: string }) {
  return (
    <section className="manifesto">
      <div className="manifesto-top"><span>{top.toUpperCase()}</span><Icon name="command" /></div>
      <p>{a}<br /><span>{b}</span></p>
      <a href={target}>{link} <Icon name="arrowRight" /></a>
      <span className="manifesto-shape" aria-hidden="true">J.</span>
    </section>
  );
}

/** Reference-style tile letter + colour, picked deterministically from the name. */
const TONES = ['black', 'lime', 'lilac', 'blue', 'orange'];
export function Mark({ name }: { name: string }) {
  const sum = Array.from(name).reduce((n, c) => n + c.charCodeAt(0), 0);
  const letter = (name.match(/[A-Za-z0-9]/)?.[0] || '#').toUpperCase();
  return <div className={`tool-mark mark-${TONES[sum % TONES.length]}`} aria-hidden="true"><span>{letter}</span><i /></div>;
}

export function FilterToggle({ open, count, label, onClick }: { open: boolean; count: number; label: string; onClick: () => void }) {
  return (
    <button className={`filter-toggle ${open ? 'filter-on' : ''}`} type="button" onClick={onClick} aria-expanded={open}>
      <Icon name="sliders" />{label}<span>{count}</span>
    </button>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="detail-eyebrow"><span className="live-dot" />{children}</div>;
}
