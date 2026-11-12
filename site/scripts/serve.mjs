// Minimal static server for out/ (port 4173). Resolves /dir/ and /dir (even with dots in the name) to index.html.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'out');
const port = Number(process.env.PORT || 4173);
const types = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon', '.png': 'image/png', '.woff2': 'font/woff2',
};

function resolveFile(urlPath) {
  let p;
  try { p = decodeURIComponent(urlPath.split('?')[0].split('#')[0]); } catch { return null; }
  const abs = path.resolve(root, '.' + p);
  if (abs !== root && !abs.startsWith(root + path.sep)) return null;
  for (const c of [abs, path.join(abs, 'index.html'), abs + '.html']) {
    try { if (fs.statSync(c).isFile()) return c; } catch { /* next */ }
  }
  return null;
}

http.createServer((req, res) => {
  const file = resolveFile(req.url || '/');
  const send = (f, code) => {
    res.writeHead(code, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    fs.createReadStream(f).pipe(res);
  };
  if (file) return send(file, 200);
  const nf = path.join(root, '404.html');
  if (fs.existsSync(nf)) return send(nf, 404);
  res.writeHead(404).end('not found');
}).listen(port, () => console.log(`serving out/ on http://localhost:${port}`));
