'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { AiDetail, AiMethod } from '@/lib/ai';
import { AI_TOOLS, bestMethod, loadAiEntry } from '@/lib/ai';
import { safeGet, safeSet } from '@/lib/store';
import { CopyButton } from './CopyButton';
import UsagePanel from './UsagePanel';
import { useI18n } from './Providers';

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
    <div className="dl-box" data-testid="install-method" data-kind={k} data-tool={tool}>
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

  if (err) return <p className="notice" role="alert">{t.ai.notFound}</p>;
  if (!d) return <p className="meta">{t.ui.loading}</p>;

  const prereq = (d.prerequisites || []).filter((p) => p !== 'none');
  const keys = d.access.api_keys_list || [];

  return (
    <article data-testid="ai-detail">
      <Link href="/ai/" className="crumb">&larr; {t.ai.back}</Link>
      <div className="app-head">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="avatar" src={d.avatar} alt={`${d.owner} avatar`} width={64} height={64} referrerPolicy="no-referrer" />
        <div>
          <h1>{d.name}</h1>
          <div className="owner">{d.owner}</div>
        </div>
      </div>
      <p data-testid="ai-desc">{d.desc}</p>
      <p className="badges">
        {d.types.map((ty) => <span key={ty} className="tbadge" data-testid="type-badge" data-type={ty}>{t.ai.types[ty] ?? ty}</span>)}
        {d.tools.map((tl) => <span key={tl} className="tool" data-testid="tool-badge" data-tool={tl}>{t.ai.tools[tl] ?? tl}</span>)}
        <span>{'★'} {d.stars}</span>
      </p>

      <section className="panel" data-testid="prereq-box">
        <h2>{t.ai.prereqTitle}</h2>
        <ul className="trust">
          {(prereq.length ? prereq : ['none']).map((p) => <li key={p}>{t.ai.prereq[p] ?? p}</li>)}
        </ul>
      </section>

      <section className="panel access" data-testid="access-box">
        <h2>{t.ai.accessTitle}</h2>
        <dl>
          <div><dt>{t.ai.accessFiles}</dt><dd data-testid="access-files">{d.access.files}</dd></div>
          <div><dt>{t.ai.accessTerminal}</dt><dd data-testid="access-terminal">{d.access.terminal}</dd></div>
          <div><dt>{t.ai.accessNetwork}</dt><dd data-testid="access-network">{d.access.network}</dd></div>
          <div>
            <dt>{t.ai.accessKeys}</dt>
            <dd data-testid="access-api_keys">
              {d.access.api_keys}
              {keys.length > 0 && (
                <ul data-testid="api-keys-list">
                  {keys.map((k) => (
                    <li key={k.name}>
                      <code>{k.name}</code> ({k.isRequired ? t.ai.keyRequired : t.ai.keyOptional}{k.isSecret ? `, ${t.ai.keySecret}` : ''})
                    </li>
                  ))}
                </ul>
              )}
            </dd>
          </div>
        </dl>
        <p className="note" data-testid="access-disclaimer">{d.access.disclaimer}</p>
      </section>

      <section className="panel" data-testid="install-box">
        <h2>{t.ai.installTitle}</h2>
        <div className="chips" role="group" aria-label={t.ai.pickTool}>
          <span className="lbl">{t.ai.pickTool}</span>
          {AI_TOOLS.map((x) => (
            <button key={x} type="button" className="chip" aria-pressed={tool === x} onClick={() => pick(x)} data-testid={`pick-${x}`}>{t.ai.tools[x]}</button>
          ))}
        </div>
        {tool ? <Method d={d} tool={tool} /> : <p className="note" data-testid="pick-hint">{t.ai.pickHint}</p>}
      </section>

      <UsagePanel d={d} tool={tool} />

      <section className="panel">
        <p className="note">{t.ai.noReadme}</p>
        <p className="note">
          <a href={d.repo_url || `https://github.com/${d.repo}`} rel="noopener noreferrer">{t.ai.repo}: {d.repo}</a>
          {d.license ? ` · ${t.ai.license}: ${d.license}` : ''}
        </p>
        <p className="note">{t.ai.sources}: {d.sources.map((s) => `${s.kind}:${s.ref}`).join(', ')}</p>
        {d.manifests_found && d.manifests_found.length > 0 && (
          <p className="note">{t.ai.manifests}: {d.manifests_found.slice(0, 12).join(', ')}</p>
        )}
      </section>
    </article>
  );
}
