import type { AppDetail, Catalog, Trending } from './types';

let catalogP: Promise<Catalog> | null = null;

export function loadCatalog(): Promise<Catalog> {
  if (!catalogP) {
    catalogP = fetch('/data/catalog.json').then((r) => {
      if (!r.ok) throw new Error('catalog ' + r.status);
      return r.json();
    });
    catalogP.catch(() => { catalogP = null; });
  }
  return catalogP;
}

/** trending.json (desktop) or trending-ai.json (AI). null when missing or unreadable. */
export async function loadTrendingDoc(file: 'trending' | 'trending-ai' = 'trending'): Promise<Trending | null> {
  try {
    const r = await fetch('/data/' + file + '.json');
    if (!r.ok) return null;
    const j = await r.json();
    return j && typeof j === 'object' ? (j as Trending) : null;
  } catch {
    return null;
  }
}

export async function loadTrendingReady(): Promise<boolean> {
  const j = await loadTrendingDoc('trending');
  return !!j && j.ready === true;
}

export async function loadApp(slug: string): Promise<AppDetail> {
  const r = await fetch('/data/apps/' + encodeURIComponent(slug) + '.json');
  if (!r.ok) throw new Error('app ' + r.status);
  return r.json();
}
