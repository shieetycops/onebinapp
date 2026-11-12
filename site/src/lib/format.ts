export function fmtNum(n: number | null | undefined): string {
  if (n == null) return '-';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 10_000) return Math.round(n / 1000) + 'k';
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(n);
}

export function fmtSize(b: number): string {
  if (!b) return '-';
  if (b >= 1024 ** 3) return (b / 1024 ** 3).toFixed(1) + ' GB';
  if (b >= 1024 ** 2) return (b / 1024 ** 2).toFixed(1) + ' MB';
  return Math.max(1, Math.round(b / 1024)) + ' KB';
}

export function fmtDate(iso: string | null | undefined, lang: string): string {
  if (!iso) return '-';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '-';
  return d.toLocaleDateString(lang === 'en' ? 'en-GB' : 'id-ID', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
}

/** Badge 'naik daun': ranked AND d7 >= max(5, 1% of stars) (same rule as scripts/catalog/trending.py has_badge). */
export function isRising(tr: { d7: number | null; rank: number | null } | null | undefined, stars: number): boolean {
  return !!tr && tr.rank != null && tr.d7 != null && tr.d7 >= Math.max(5, 0.01 * stars);
}

export function fill(s: string, vars: Record<string, string | number>): string {
  return s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''));
}
