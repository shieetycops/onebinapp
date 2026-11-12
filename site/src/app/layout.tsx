import type { Metadata, Viewport } from 'next';
import Providers from '@/components/Providers';
import { Header, Footer } from '@/components/Chrome';
import './globals.css';

export const metadata: Metadata = {
  title: 'Jembatan Rilis',
  description: 'Katalog app dari rilis GitHub dengan unduhan langsung ke OS Anda.',
};

export const viewport: Viewport = { width: 'device-width', initialScale: 1 };

const themeScript = `try{var s=localStorage.getItem('jr-theme');var d=s?s==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.setAttribute('data-theme',d?'dark':'light')}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Providers>
          <Header />
          <main className="wrap" id="main">{children}</main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
