'use client';

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { id } from '@/i18n/id';
import { en } from '@/i18n/en';
import type { Dict } from '@/i18n/id';
import { safeGet, safeSet } from '@/lib/store';

export type Lang = 'id' | 'en';
type Theme = 'light' | 'dark';

interface Ctx {
  lang: Lang;
  t: Dict;
  setLang: (l: Lang) => void;
  theme: Theme;
  toggleTheme: () => void;
}

const LangCtx = createContext<Ctx>({ lang: 'id', t: id, setLang: () => {}, theme: 'light', toggleTheme: () => {} });

export function useI18n() {
  return useContext(LangCtx);
}

export default function Providers({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>('id');
  const [theme, setTheme] = useState<Theme>('light');

  useEffect(() => {
    const saved = safeGet('jr-lang');
    if (saved === 'en' || saved === 'id') setLangState(saved);
    const th = document.documentElement.getAttribute('data-theme');
    setTheme(th === 'dark' ? 'dark' : 'light');
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    safeSet('jr-lang', l);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((cur) => {
      const next: Theme = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      safeSet('jr-theme', next);
      return next;
    });
  }, []);

  return <LangCtx.Provider value={{ lang, t: lang === 'en' ? en : id, setLang, theme, toggleTheme }}>{children}</LangCtx.Provider>;
}
