import fs from 'node:fs';
import path from 'node:path';
import AppView from '@/components/AppView';

export const dynamicParams = false;

export function generateStaticParams() {
  const dir = process.env.DATA_DIR || path.join(process.cwd(), 'public', 'data');
  const cat = JSON.parse(fs.readFileSync(path.join(dir, 'catalog.json'), 'utf8')) as { apps: { slug: string }[] };
  return cat.apps.map((a) => ({ slug: a.slug }));
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <AppView slug={slug} />;
}
