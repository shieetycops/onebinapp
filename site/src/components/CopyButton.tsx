'use client';

import { useState } from 'react';
import { useI18n } from './Providers';

export function CopyButton({ text, testid = 'copy-btn' }: { text: string; testid?: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<'idle' | 'ok' | 'fail'>('idle');

  async function copy() {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      try {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        ok = document.execCommand('copy');
        document.body.removeChild(ta);
      } catch { ok = false; }
    }
    setState(ok ? 'ok' : 'fail');
    setTimeout(() => setState('idle'), 2000);
  }

  return (
    <button type="button" className="btn" onClick={copy} data-testid={testid} aria-live="polite">
      {state === 'ok' ? t.ai.copied : state === 'fail' ? t.ai.copyFail : t.ai.copy}
    </button>
  );
}
