import fs from 'node:fs';
import path from 'node:path';
import AiView from '@/components/AiView';

export const dynamicParams = false;

export function generateStaticParams() {
  const dir = process.env.DATA_DIR || path.join(process.cwd(), 'public', 'data');
  const cat = JSON.parse(fs.readFileSync(path.join(dir, 'catalog-ai.json'), 'utf8')) as { entries: { slug: string }[] };
  return cat.entries.map((e) => ({ slug: e.slug }));
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <AiView slug={slug} />;
}
