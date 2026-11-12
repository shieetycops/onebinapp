const KEY = 'jr-mine';

export function readMine(): string[] {
  try {
    const raw = localStorage.getItem(KEY);
    const v = raw ? JSON.parse(raw) : [];
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

export function writeMine(list: string[]): boolean {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
    return true;
  } catch {
    return false;
  }
}

export function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function safeSet(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: ignore */
  }
}
