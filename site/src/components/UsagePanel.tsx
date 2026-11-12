'use client';

import type { AiDetail, UsageAbility, UsageGap, UsageSteps } from '@/lib/ai';
import { bestMethod } from '@/lib/ai';
import { CopyButton } from './CopyButton';
import { useI18n } from './Providers';

/* Everything here is rendered as plain React text. Nothing from a repo is ever parsed as HTML or markdown. */

const CMD = /^(claude|codex) /;

function Step({ s }: { s: string }) {
  if (CMD.test(s)) {
    return (
      <>
        <pre className="code" data-testid="use-cmd">{s}</pre>
        <div className="row"><CopyButton text={s} testid="use-copy" /></div>
      </>
    );
  }
  const parts = s.split('`');
  return <>{parts.map((p, i) => (i % 2 ? <code key={i}>{p}</code> : <span key={i}>{p}</span>))}</>;
}

function Unavail({ text, readme, id }: { text: string; readme?: string; id: string }) {
  const { t } = useI18n();
  return (
    <p className="note" data-testid={id}>
      {text}
      {readme && (
        <> {' '}<a href={readme} rel="noopener noreferrer" data-testid="use-readme-link">{t.ai.useReadmeLink}</a></>
      )}
    </p>
  );
}

function StepsPart({ part, id }: { part?: UsageSteps | UsageGap; id: string }) {
  const { t } = useI18n();
  if (!part || part.ok !== true) return <Unavail id={id + '-na'} text={t.ai.useNoDocs} />;
  const p = part as UsageSteps;
  return (
    <div data-testid={id}>
      <ol className="steps">
        {p.steps.map((s, i) => <li key={i}><Step s={s} /></li>)}
      </ol>
      {p.inferred && <p className="note" data-testid={id + '-inferred'}>{t.ai.useInferred}</p>}
      {p.note && <p className="note">{p.note}</p>}
      {p.config_file && <p className="note">{t.ai.useSettingsPut}: <code>{p.config_file}</code></p>}
      <p className="note"><a href={p.source_url} rel="noopener noreferrer" data-testid={id + '-source'}>{t.ai.source}</a></p>
    </div>
  );
}

function Abilities({ a, readme }: { a?: UsageAbility; readme: string }) {
  const { t } = useI18n();
  if (!a || !a.ok) return <Unavail id="use-can-na" text={t.ai.useUnavailable} readme={a?.readme_url || readme} />;
  if (a.kind === 'plugin') {
    return (
      <div data-testid="use-can">
        {a.commands && a.commands.length > 0 && (
          <>
            <h4>{t.ai.useCommands}</h4>
            <ul className="trust">{a.commands.map((c) => <li key={c.name}><code>/{c.name}</code>{c.desc ? `: ${c.desc}` : ''}</li>)}</ul>
          </>
        )}
        {a.agents && a.agents.length > 0 && (
          <>
            <h4>{t.ai.useAgents}</h4>
            <ul className="trust">{a.agents.map((c) => <li key={c.name}><code>{c.name}</code>{c.desc ? `: ${c.desc}` : ''}</li>)}</ul>
          </>
        )}
        {a.hooks && a.hooks.length > 0 && (
          <>
            <h4>{t.ai.useHooks}</h4>
            <ul className="trust">{a.hooks.map((h, i) => <li key={i}><code>{h.event}</code>{h.matcher ? ` (${h.matcher})` : ''}: <code>{h.command}</code></li>)}</ul>
          </>
        )}
        <p className="note">{t.ai.usePluginSrc}</p>
      </div>
    );
  }
  const head = a.kind === 'tools' ? t.ai.useTools : t.ai.useSkills;
  return (
    <div data-testid="use-can">
      <h4>{head}</h4>
      <ul className="trust">
        {(a.items || []).map((c) => <li key={c.name}><code>{c.name}</code>{c.desc ? `: ${c.desc}` : ''}</li>)}
      </ul>
      <p className="note">{a.kind === 'tools' ? t.ai.useRegistryTools : t.ai.useSkillSrc}</p>
    </div>
  );
}

export default function UsagePanel({ d, tool }: { d: AiDetail; tool: string | null }) {
  const { t } = useI18n();
  const u = d.usage;
  const readme = u?.readme_url || `https://github.com/${d.repo}#readme`;
  if (!tool) {
    return (
      <section className="panel" data-testid="usage-box">
        <h2>{t.ai.useTitle}</h2>
        <p className="note" data-testid="use-pick-hint">{t.ai.usePickTool}</p>
      </section>
    );
  }
  const { type } = bestMethod(d, tool);
  const cell = type ? u?.by_tool?.[tool]?.[type] : undefined;
  const settings = u?.settings;
  const showSettings = type === 'mcp';
  return (
    <section className="panel" data-testid="usage-box" data-tool={tool} data-type={type ?? ''}>
      <h2>{t.ai.useTitle}</h2>
      <p className="note">{t.ai.useTextOnly}</p>

      <h3>{t.ai.useAfter}</h3>
      {type ? <StepsPart part={cell?.after} id="use-after" /> : <Unavail id="use-after-na" text={t.ai.none} />}

      <h3>{t.ai.useCan}</h3>
      {type ? <Abilities a={u?.abilities?.[type]} readme={readme} /> : <Unavail id="use-can-na" text={t.ai.useUnavailable} readme={readme} />}

      <h3>{t.ai.useExamples}</h3>
      {u?.examples?.ok && u.examples.items?.length ? (
        <div data-testid="use-examples" data-auto={u.examples.auto ? '1' : '0'}>
          <ul className="trust">{u.examples.items.map((e, i) => <li key={i} data-testid="use-example">{e}</li>)}</ul>
          <p className="note" data-testid="use-example-label">{u.examples.auto ? t.ai.useAutoExample : t.ai.useFromReadme}</p>
        </div>
      ) : (
        <Unavail id="use-examples-na" text={t.ai.useUnavailable} readme={readme} />
      )}

      {showSettings && (
        <>
          <h3>{t.ai.useSettings}</h3>
          {settings?.ok && settings.items && settings.items.length > 0 ? (
            <div data-testid="use-settings">
              <ul className="trust">
                {settings.items.map((s) => (
                  <li key={s.name}>
                    <code>{s.name}</code> ({s.required ? t.ai.keyRequired : t.ai.keyOptional}{s.secret ? `, ${t.ai.keySecret}` : ''})
                    {s.where ? <> {' '}{t.ai.useSettingsNote}: {s.where}</> : <> {' '}({t.ai.useUnavailable})</>}
                  </li>
                ))}
              </ul>
              <StepsPart part={cell?.settings} id="use-settings-where" />
            </div>
          ) : settings?.ok && settings.none_listed ? (
            <p className="note" data-testid="use-settings-none">{t.ai.useSettingsNone}</p>
          ) : (
            <Unavail id="use-settings-na" text={t.ai.useUnavailable} readme={readme} />
          )}
        </>
      )}

      <h3>{t.ai.useRemove}</h3>
      {type ? <StepsPart part={cell?.uninstall} id="use-remove" /> : <Unavail id="use-remove-na" text={t.ai.none} />}
    </section>
  );
}
