'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { AiDetail, AiMethod } from '@/lib/ai';
import { AI_TOOLS, bestMethod, loadAiEntry } from '@/lib/ai';
import { safeGet, safeSet } from '@/lib/store';
import { CopyButton } from './CopyButton';
import UsagePanel from './UsagePanel';
import { useI18n } from './Providers';
import { Eyebrow, Icon } from './Ui';

const KEY = 'jr-ai-tool';

function SnippetPaths({ m }: { m: AiMethod }) {
  const { t } = useI18n();
  const paths = m.file_path_by_os && Object.keys(m.file_path_by_os).length ? m.file_path_by_os : null;
  return (
    <div data-testid="snippet-paths">
      <p style={{ margin: '0 0 4px' }}><strong>{t.ai.pasteInto}</strong></p>
      {m.file_path && <p data-testid="snippet-file"><code>{m.file_path}</code></p>}
      {paths ? (
        <ul className="steps">
          {Object.entries(paths).map(([os, p]) => (
            <li key={os}>{t.ai.osNames[os] ?? os}: <code>{p}</code></li>
          ))}
        </ul>
      ) : (
        <p className="note">{t.ai.osPathNone}</p>
      )}
    </div>
  );
}

function Method({ d, tool }: { d: AiDetail; tool: string }) {
  const { t } = useI18n();
  const { type, method: m } = bestMethod(d, tool);
  const k = m.kind;
  const lines = (m.text || '').split('\n').filter((l) => l.trim());
  return (
    <div className="command-card" data-testid="install-method" data-kind={k} data-tool={tool}>
      {k === 'none' ? (
        <p data-testid="install-none">{t.ai.none}</p>
      ) : (
        <>
          <h3>
            {k === 'oneclick' ? t.ai.oneclickLabel : k === 'oneline' ? t.ai.onelineLabel : k === 'snippet' ? t.ai.snippetLabel : t.ai.manualLabel}
            {type && <span className="note"> ({t.ai.methodType}: {t.ai.types[type] ?? type})</span>}
          </h3>
          {k !== 'oneclick' && m.label && <p data-testid="method-label" style={{ margin: 0 }}>{m.label}</p>}
          {m.prerequisites_plain && m.prerequisites_plain.length > 0 && (
            <ul className="trust" data-testid="method-prereq">
              {m.prerequisites_plain.map((p, i) => <li key={i}>{p}</li>)}
            </ul>
          )}
          {k === 'oneclick' && m.url && (
            <div className="dl-actions">
              <a className="btn primary" href={m.url} data-testid="oneclick-link">{m.label || t.ai.oneclickLabel}</a>
            </div>
          )}
          {(k === 'oneline' || k === 'snippet') && m.text && (
            <>
              <pre className="code" data-testid="install-text">{m.text}</pre>
              <div className="row"><CopyButton text={m.text} /></div>
            </>
          )}
          {k === 'snippet' && <SnippetPaths m={m} />}
          {k === 'manual' && (
            <ol className="steps" data-testid="manual-steps">
              {lines.map((l, i) => <li key={i}>{l}</li>)}
            </ol>
          )}
          {m.note && <p className="note" data-testid="method-note">{m.note}</p>}
          {m.source_url && (
            <p className="note"><a href={m.source_url} rel="noopener noreferrer" data-testid="method-source">{t.ai.source}</a></p>
          )}
        </>
      )}
    </div>
  );
}

export default function AiView({ slug }: { slug: string }) {
  const { t } = useI18n();
  const [d, setD] = useState<AiDetail | null>(null);
  const [err, setErr] = useState(false);
  const [tool, setTool] = useState<string | null>(null);

  useEffect(() => {
    loadAiEntry(slug).then(setD).catch(() => setErr(true));
    const saved = safeGet(KEY);
    if (saved && (AI_TOOLS as readonly string[]).includes(saved)) setTool(saved);
  }, [slug]);

  function pick(x: string) {
    setTool(x);
    safeSet(KEY, x);
  }

  if (err) return <><Link href="/ai/" className="back-link"><Icon name="arrowLeft" size={15} /> {t.ai.back}</Link><p className="notice" role="alert">{t.ai.notFound}</p></>;
  if (!d) return <p className="meta">{t.ui.loading}</p>;

  const prereq = (d.prerequisites || []).filter((p) => p !== 'none');
  const keys = d.access.api_keys_list || [];

  return (
    <div data-testid="ai-detail">
      <Link href="/ai/" className="back-link"><Icon name="arrowLeft" size={15} /> {t.ai.back}</Link>
      <section className="skill-hero">
        <div className="skill-identity">
          <div className="skill-glyph" aria-hidden="true"><Icon name="command" /></div>
          <div>
            <Eyebrow>{(t.ai.categories[d.category] ?? d.category ?? '').toUpperCase()}</Eyebrow>
            <h1>{d.name}</h1>
            <p className="app-owner">{d.owner}</p>
          </div>
        </div>
        <p className="skill-deck" data-testid="ai-desc">{d.desc}</p>
        <div className="skill-metadata">
          {d.types.map((ty) => <span key={ty} className="metadata-kind" data-testid="type-badge" data-type={ty}>{t.ai.types[ty] ?? ty}</span>)}
          {d.tools.map((tl) => <span key={tl} data-testid="tool-badge" data-tool={tl}>{t.ai.tools[tl] ?? tl}</span>)}
          <span className="metadata-stars"><Icon name="star" fill /> {d.stars}</span>
        </div>
      </section>

      <div className="skill-overview-grid">
        <section className="prep-panel" data-testid="prereq-box">
          <div className="section-stamp"><span>01</span><h2>{t.ai.prereqTitle}</h2></div>
          <ul className="trust-list" style={{ marginTop: 16 }}>
            {(prereq.length ? prereq : ['none']).map((p) => <li key={p}>{t.ai.prereq[p] ?? p}</li>)}
          </ul>
        </section>

        <section className="access-panel" data-testid="access-box">
          <div className="section-stamp"><span>02</span><h2>{t.ai.accessTitle}</h2></div>
          <div className="access-grid">
            <div><span>{t.ai.accessFiles.toUpperCase()}</span><strong data-testid="access-files">{d.access.files}</strong></div>
            <div><span>{t.ai.accessTerminal.toUpperCase()}</span><strong data-testid="access-terminal">{d.access.terminal}</strong></div>
            <div><span>{t.ai.accessNetwork.toUpperCase()}</span><strong data-testid="access-network">{d.access.network}</strong></div>
            <div>
              <span>{t.ai.accessKeys.toUpperCase()}</span>
              <strong data-testid="access-api_keys">{d.access.api_keys}</strong>
              {keys.length > 0 && (
                <ul data-testid="api-keys-list" className="key-list">
                  {keys.map((k) => (
                    <li key={k.name}>
                      <code>{k.name}</code> ({k.isRequired ? t.ai.keyRequired : t.ai.keyOptional}{k.isSecret ? `, ${t.ai.keySecret}` : ''})
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
          <p className="access-note" data-testid="access-disclaimer">{d.access.disclaimer}</p>
        </section>
      </div>

      <section className="install-panel" data-testid="install-box">
        <div className="install-heading">
          <div><Eyebrow>03</Eyebrow><h2>{t.ai.installTitle}</h2></div>
          <span className="install-illustration"><Icon name="command" /></span>
        </div>
        <div className="client-picker" role="group" aria-label={t.ai.pickTool}>
          <span className="picker-label">{t.ai.pickTool.toUpperCase()}</span>
          <div className="client-tabs">
            {AI_TOOLS.map((x) => (
              <button key={x} type="button" aria-pressed={tool === x} className={tool === x ? 'client-active' : ''} onClick={() => pick(x)} data-testid={`pick-${x}`}>{t.ai.tools[x]}</button>
            ))}
          </div>
        </div>
        {tool ? <Method d={d} tool={tool} /> : <p className="note" data-testid="pick-hint">{t.ai.pickHint}</p>}
      </section>

      <UsagePanel d={d} tool={tool} />

      <section className="source-panel">
        <div className="source-icon"><Icon name="branch" /></div>
        <div>
          <Eyebrow>{t.ai.repo.toUpperCase()}</Eyebrow>
          <p>{t.ai.noReadme}</p>
          <a className="text-link" href={d.repo_url || `https://github.com/${d.repo}`} rel="noopener noreferrer">{t.ai.repo}: {d.repo} <Icon name="arrowUpRight" /></a>
          <p style={{ marginTop: 8 }}>{t.ai.sources}: {d.sources.map((s) => `${s.kind}:${s.ref}`).join(', ')}</p>
          {d.manifests_found && d.manifests_found.length > 0 && <p>{t.ai.manifests}: {d.manifests_found.slice(0, 12).join(', ')}</p>}
        </div>
        <div className="source-meta">{d.license && <span>{t.ai.license.toUpperCase()} <b>{d.license}</b></span>}</div>
      </section>
    </div>
  );
}
