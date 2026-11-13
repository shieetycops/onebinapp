export type OS = 'windows' | 'macos' | 'linux' | 'android';
export type VisitorOS = OS | 'ios' | 'other';

export interface Trust {
  curated_rules?: boolean;
  rules?: string;
  has_checksum_asset?: boolean;
  source?: string;
  picker?: string;
}

export interface Card {
  slug: string;
  repo: string;
  name: string;
  owner: string;
  avatar: string;
  desc: string;
  stars: number;
  platforms: OS[];
  category: string;
  dev: boolean;
  latest_release_at: string | null;
  is_new: boolean;
  version: string;
  trust: Trust;
  trending: { d7: number | null; d30: number | null; rank: number | null };
  sources?: string[];
}

export interface Catalog {
  generated_at: string;
  count: number;
  apps: Card[];
}

export interface Asset {
  name: string;
  size: number;
  downloads: number;
  url: string;
  os: string;
  arch: string;
  kind: string;
}

export interface Release {
  tag: string;
  name: string;
  prerelease: boolean;
  published_at: string;
  notes_md: string;
  assets: Asset[];
  picks: Record<string, string | null>;
}

export interface AppDetail extends Card {
  homepage: string | null;
  license: string | null;
  topics: string[];
  forks: number;
  downloads_total: number;
  releases: Release[];
}

export interface Trending {
  ready: boolean;
  /** Top gainers of the last day (1 to 2 days between snapshots). Absent in older builds. */
  daily?: { ready: boolean; baseline: string | null; items: { slug: string; d1: number }[] };
  sources_used?: string[];
  github_trending?: { enabled: boolean; ok: boolean; fetched_at?: string | null };
}

export const CATEGORIES = ['media', 'produktivitas', 'ai', 'privasi', 'jaringan', 'sosial', 'baca', 'alat', 'game', 'developer'] as const;
export const PLATFORMS: OS[] = ['windows', 'macos', 'linux', 'android'];
