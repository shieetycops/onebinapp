import { loadTrendingDoc } from './data';
export const AI_TOOLS = ['claude-code', 'claude-desktop', 'cursor', 'vscode', 'codex'] as const;
export type AiTool = (typeof AI_TOOLS)[number];
export const AI_TYPES = ['mcp', 'skill', 'plugin'] as const;
export type AiType = (typeof AI_TYPES)[number];
export const AI_CATEGORIES = ['coding', 'data', 'web', 'files', 'devops', 'search', 'memory', 'other'] as const;
export type MethodKind = 'oneclick' | 'oneline' | 'snippet' | 'manual' | 'none';
const RANK: MethodKind[] = ['oneclick', 'oneline', 'snippet', 'manual', 'none'];

export interface AiAccess {
  files: string;
  terminal: string;
  network: string;
  api_keys: string;
  api_keys_list: { name: string; isRequired?: boolean; isSecret?: boolean }[];
  disclaimer: string;
}

export interface AiCard {
  slug: string;
  repo: string;
  name: string;
  owner: string;
  avatar: string;
  desc: string;
  stars: number;
  types: string[];
  tools: string[];
  category: string;
  prerequisites: string[];
  latest_activity_at: string | null;
  sources: { kind: string; ref: string }[];
  install_summary: Record<string, boolean>;
  access: AiAccess;
  trending: { ready?: boolean; d7: number | null; d30: number | null; rank: number | null };
}

export async function loadAiTrendingReady(): Promise<boolean> {
  const j = await loadTrendingDoc('trending-ai');
  return !!j && j.ready === true;
}

export interface AiCatalog {
  generated_at: string;
  count: number;
  entries: AiCard[];
}

export interface AiMethod {
  kind: MethodKind;
  label?: string;
  note?: string;
  text?: string | null;
  url?: string | null;
  file_path_by_os?: Record<string, string>;
  file_path?: string | null;
  prerequisites_plain?: string[];
  source_url?: string | null;
}

export interface UsageGap { ok: false; unavailable?: boolean; na?: boolean; doc_gap?: boolean; readme_url?: string }
export interface UsageSteps { ok: true; steps: string[]; source_url: string; config_file?: string | null; note?: string | null; inferred?: boolean }
export type UsageItem = { name: string; desc?: string | null };
export interface UsageAbility {
  ok: boolean; unavailable?: boolean; readme_url?: string; kind?: string; source?: string;
  items?: UsageItem[]; commands?: UsageItem[]; agents?: UsageItem[];
  hooks?: { event: string; matcher?: string | null; command: string }[];
}
export interface UsageSetting { name: string; required: boolean; secret: boolean; where?: string | null; header?: boolean }
export interface AiUsage {
  readme_url: string;
  abilities: Record<string, UsageAbility>;
  examples: { ok: boolean; unavailable?: boolean; auto?: boolean; source?: string; items?: string[]; readme_url?: string };
  settings: { ok: boolean; na?: boolean; unavailable?: boolean; none_listed?: boolean; items?: UsageSetting[]; readme_url?: string };
  by_tool: Record<string, Record<string, { after?: UsageSteps | UsageGap; uninstall?: UsageSteps | UsageGap; settings?: UsageSteps | UsageGap }>>;
}

export interface AiDetail extends AiCard {
  usage?: AiUsage;
  repo_url?: string;
  homepage?: string | null;
  license?: string | null;
  topics?: string[];
  forks?: number;
  manifests_found?: string[];
  install?: Record<string, Record<string, AiMethod>>;
}

let catP: Promise<AiCatalog> | null = null;
export function loadAiCatalog(): Promise<AiCatalog> {
  if (!catP) {
    catP = fetch('/data/catalog-ai.json').then((r) => {
      if (!r.ok) throw new Error('catalog-ai ' + r.status);
      return r.json();
    });
    catP.catch(() => { catP = null; });
  }
  return catP;
}

export async function loadAiEntry(slug: string): Promise<AiDetail> {
  const r = await fetch('/data/ai/' + encodeURIComponent(slug) + '.json');
  if (!r.ok) throw new Error('ai ' + r.status);
  return r.json();
}

const SAFE_URL = /^(cursor|vscode|vscode-insiders|https):/i;

/** Best method for one tool across the entry's types: oneclick > oneline > snippet > manual > none. */
export function bestMethod(d: AiDetail, tool: string): { type: string | null; method: AiMethod } {
  const byType = d.install?.[tool] || {};
  let best: { type: string | null; method: AiMethod } | null = null;
  for (const type of Object.keys(byType)) {
    const m = byType[type];
    if (!m || !RANK.includes(m.kind)) continue;
    if (m.kind === 'oneclick' && !(m.url && SAFE_URL.test(m.url))) continue;
    if ((m.kind === 'oneline' || m.kind === 'snippet' || m.kind === 'manual') && !m.text) continue;
    if (!best || RANK.indexOf(m.kind) < RANK.indexOf(best.method.kind)) best = { type, method: m };
  }
  return best || { type: null, method: { kind: 'none' } };
}
