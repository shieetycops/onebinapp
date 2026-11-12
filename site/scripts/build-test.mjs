// Test build: static export whose out/data is the fixture tree. public/data is never modified.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const site = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const fixtures = path.join(site, 'tests', 'fixtures', 'data');
const env = { ...process.env, DATA_DIR: fixtures };
const r = spawnSync('npx', ['next', 'build'], { cwd: site, env, stdio: 'inherit', shell: true });
if (r.status !== 0) process.exit(r.status ?? 1);
const out = path.join(site, 'out');
fs.rmSync(path.join(out, 'data'), { recursive: true, force: true });
fs.cpSync(fixtures, path.join(out, 'data'), { recursive: true });
console.log('out/data replaced with fixtures');
