import type { VisitorOS } from './types';

interface UAData {
  platform?: string;
}

export function osFromStrings(uaDataPlatform: string | undefined, ua: string): VisitorOS {
  const p = (uaDataPlatform || '').toLowerCase();
  if (p) {
    if (p.includes('android')) return 'android';
    if (p.includes('windows')) return 'windows';
    if (p.includes('macos') || p === 'mac') return 'macos';
    if (p.includes('ios')) return 'ios';
    if (p.includes('linux') || p.includes('chrome os')) return 'linux';
  }
  // Order matters: Android UAs contain "Linux"; iOS UAs contain "like Mac OS X".
  if (/android/i.test(ua)) return 'android';
  if (/iphone|ipad|ipod/i.test(ua)) return 'ios';
  if (/windows/i.test(ua)) return 'windows';
  if (/macintosh|mac os x/i.test(ua)) return 'macos';
  if (/linux|x11|cros/i.test(ua)) return 'linux';
  return 'other';
}

export function detectOS(): VisitorOS {
  if (typeof navigator === 'undefined') return 'other';
  const uad = (navigator as Navigator & { userAgentData?: UAData }).userAgentData;
  return osFromStrings(uad?.platform, navigator.userAgent || '');
}
