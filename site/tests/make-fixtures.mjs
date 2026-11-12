// Generates tests/fixtures/data/* in the exact shape of the real catalog. Run: node tests/make-fixtures.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures', 'data');
fs.rmSync(root, { recursive: true, force: true });
fs.mkdirSync(path.join(root, 'apps'), { recursive: true });

const trust = {
  curated_rules: true, rules: 'C1-C4b', has_checksum_asset: false,
  source: 'GitHub release, direct link',
  picker: 'picked by name only (evaluated on 300+ repos, not a safety check)',
};
const up = (o, r, n) => `https://github.com/${o}/${r}/releases/download/v1/${n}`;
const asset = (o, r, name, os, arch, kind, tag = 'v1') => ({
  name, size: 12_345_678, downloads: 42, url: `https://github.com/${o}/${r}/releases/download/${tag}/${name}`, os, arch, kind,
});
const ALL = ['windows-x64', 'windows-arm64', 'macos-arm64', 'macos-x64', 'linux-x64', 'linux-arm64', 'android'];
const picks = (o) => Object.fromEntries(ALL.map((k) => [k, o[k] ?? null]));

const apps = [];
function add(def) {
  const [owner, repo] = def.repo.split('/');
  const slug = `${owner}--${repo}`.toLowerCase();
  const releases = def.releases.map((r) => ({
    tag: r.tag, name: r.tag, prerelease: !!r.prerelease, published_at: r.at, notes_md: r.notes ?? '',
    assets: r.assets, picks: picks(r.picks || {}),
  }));
  const card = {
    slug, repo: def.repo, name: def.name || repo, owner, avatar: `https://avatars.githubusercontent.com/u/${def.id || 1}?v=4`,
    desc: def.desc || `Fixture app ${repo}`, stars: def.stars, platforms: def.platforms, category: def.category || 'alat',
    dev: !!def.dev, latest_release_at: def.releases[0].at, is_new: false, version: def.version || def.releases[0].tag,
    trust, trending: { d7: null, d30: null, rank: null },
  };
  apps.push(card);
  const detail = { ...card, homepage: 'https://example.com', license: 'MIT', topics: [], forks: 7, downloads_total: 123456, releases };
  fs.writeFileSync(path.join(root, 'apps', slug + '.json'), JSON.stringify(detail));
}

// 1 exact pick on Windows (+ Linux), with older and pre-release versions
add({
  repo: 'acme/winpad', name: 'WinPad', stars: 5000, version: 'v2.0.0', platforms: ['windows', 'linux'], category: 'produktivitas',
  releases: [
    { tag: 'v2.1.0-beta', prerelease: true, at: '2026-11-08T10:00:00Z', notes: 'Beta notes',
      assets: [asset('acme', 'winpad', 'WinPad-2.1.0-beta-Setup.exe', 'windows', 'x64', 'exe', 'v2.1.0-beta')], picks: { 'windows-x64': 'WinPad-2.1.0-beta-Setup.exe' } },
    { tag: 'v2.0.0', at: '2026-11-01T10:00:00Z', notes: '## Baru\n\n- Fitur **tebal**\n- [Tautan](https://example.com)\n',
      assets: [
        asset('acme', 'winpad', 'WinPad-2.0.0-Setup.exe', 'windows', 'x64', 'exe', 'v2.0.0'),
        asset('acme', 'winpad', 'WinPad-2.0.0.AppImage', 'linux', 'x64', 'appimage', 'v2.0.0'),
      ],
      picks: { 'windows-x64': 'WinPad-2.0.0-Setup.exe', 'linux-x64': 'WinPad-2.0.0.AppImage' } },
    { tag: 'v1.0.0', at: '2026-06-01T10:00:00Z', notes: 'Old',
      assets: [asset('acme', 'winpad', 'WinPad-1.0.0-Setup.exe', 'windows', 'x64', 'exe', 'v1.0.0')], picks: { 'windows-x64': 'WinPad-1.0.0-Setup.exe' } },
  ],
});

// 2 picker silent: windows+macOS assets exist, no picks
add({
  repo: 'acme/silentapp', name: 'SilentApp', stars: 4000, platforms: ['windows', 'macos'],
  releases: [{ tag: 'v3.0.0', at: '2026-10-30T10:00:00Z', notes: 'x',
    assets: [
      asset('acme', 'silentapp', 'silentapp-win.exe', 'windows', 'unknown', 'exe', 'v3.0.0'),
      asset('acme', 'silentapp', 'silentapp-mac.dmg', 'macos', 'unknown', 'dmg', 'v3.0.0'),
    ], picks: {} }],
});

// 3 mac with separate arm64/x64
add({
  repo: 'acme/macsplit', name: 'MacSplit', stars: 3000, platforms: ['macos'],
  releases: [{ tag: 'v1.2.0', at: '2026-10-25T10:00:00Z', notes: 'x',
    assets: [
      asset('acme', 'macsplit', 'MacSplit-arm64.dmg', 'macos', 'arm64', 'dmg', 'v1.2.0'),
      asset('acme', 'macsplit', 'MacSplit-x64.dmg', 'macos', 'x64', 'dmg', 'v1.2.0'),
    ], picks: { 'macos-arm64': 'MacSplit-arm64.dmg', 'macos-x64': 'MacSplit-x64.dmg' } }],
});

// 4 mac universal: same asset for both cells
add({
  repo: 'acme/macuniversal', name: 'MacUniversal', stars: 2900, platforms: ['macos'],
  releases: [{ tag: 'v1.0.0', at: '2026-10-24T10:00:00Z', notes: 'x',
    assets: [asset('acme', 'macuniversal', 'MacUniversal.dmg', 'macos', 'universal', 'dmg', 'v1.0.0')],
    picks: { 'macos-arm64': 'MacUniversal.dmg', 'macos-x64': 'MacUniversal.dmg' } }],
});

// 5 APK only
add({
  repo: 'acme/androidonly', name: 'AndroidOnly', stars: 2800, platforms: ['android'],
  releases: [{ tag: 'v0.9.0', at: '2026-10-20T10:00:00Z', notes: 'x',
    assets: [asset('acme', 'androidonly', 'androidonly-0.9.0.apk', 'android', 'universal', 'apk', 'v0.9.0')],
    picks: { android: 'androidonly-0.9.0.apk' } }],
});

// 6 Linux only (no build for Windows/macOS visitors)
add({
  repo: 'acme/linuxonly', name: 'LinuxOnly', stars: 2700, platforms: ['linux'],
  releases: [{ tag: 'v5.0.0', at: '2026-10-18T10:00:00Z', notes: 'x',
    assets: [asset('acme', 'linuxonly', 'linuxonly-5.0.0.AppImage', 'linux', 'x64', 'appimage', 'v5.0.0')],
    picks: { 'linux-x64': 'linuxonly-5.0.0.AppImage' } }],
});

// 7 developer category
add({
  repo: 'acme/devtool', name: 'DevTool', stars: 9000, platforms: ['windows'], category: 'developer', dev: true,
  releases: [{ tag: 'v1.0.0', at: '2026-11-05T10:00:00Z', notes: 'x',
    assets: [asset('acme', 'devtool', 'DevTool-Setup.exe', 'windows', 'x64', 'exe', 'v1.0.0')], picks: { 'windows-x64': 'DevTool-Setup.exe' } }],
});

// 8 hostile release notes
add({
  repo: 'acme/xssnotes', name: 'XssNotes', stars: 2600, platforms: ['windows'],
  releases: [{ tag: 'v1.0.0', at: '2026-10-17T10:00:00Z',
    notes: [
      'Hello <script>window.__xss = 1</script> world',
      '',
      '<img src="x" onerror="window.__xss = 2">',
      '',
      '<iframe src="https://example.com"></iframe>',
      '',
      '[klik](javascript:window.__xss=3)',
      '',
      '<b id="rawbold">raw bold</b>',
      '',
      'Plain **markdown bold** stays.',
    ].join('\n'),
    assets: [asset('acme', 'xssnotes', 'XssNotes-Setup.exe', 'windows', 'x64', 'exe', 'v1.0.0')], picks: { 'windows-x64': 'XssNotes-Setup.exe' } }],
});

// 9 dotted repo name (slug contains a dot -> directory name with a dot)
add({
  repo: 'acme/dotted.js', name: 'Dotted.js', stars: 2500, platforms: ['windows'],
  releases: [{ tag: 'v1.0.0', at: '2026-10-16T10:00:00Z', notes: 'x',
    assets: [asset('acme', 'dotted.js', 'dotted-Setup.exe', 'windows', 'x64', 'exe', 'v1.0.0')], picks: { 'windows-x64': 'dotted-Setup.exe' } }],
});

// filler for pagination (60 Windows apps)
for (let i = 0; i < 60; i++) {
  const n = String(i).padStart(2, '0');
  add({
    repo: `filler/app${n}`, name: `Filler ${n}`, stars: 100 + i, platforms: ['windows'],
    releases: [{ tag: 'v1.0.0', at: `2026-09-${String(1 + (i % 28)).padStart(2, '0')}T10:00:00Z`, notes: 'x',
      assets: [asset('filler', `app${n}`, `filler${n}.exe`, 'windows', 'x64', 'exe', 'v1.0.0')], picks: { 'windows-x64': `filler${n}.exe` } }],
  });
}

fs.writeFileSync(path.join(root, 'catalog.json'), JSON.stringify({ generated_at: '2026-11-11T00:00:00Z', picker_sha256: 'fixture', count: apps.length, apps }));
fs.writeFileSync(path.join(root, 'trending.json'), JSON.stringify({ ready: false, generated_at: '2026-11-11T00:00:00Z', window_days: { d7: 7, d30: 30 }, items: [], badges: 0, sources_used: ['stars_history'], snapshot_dates: ['2026-11-11'], baseline_dates: { 7: null, 30: null }, github_trending: { enabled: false, ok: false, fetched_at: null, daily: [], weekly: [] } }));
fs.writeFileSync(path.join(root, 'stats.json'), JSON.stringify({ count: apps.length }));
console.log('fixtures:', apps.length, 'apps');

// ---- AI fixtures (shape of site/public/data/catalog-ai.json, stats-ai.json, ai/<slug>.json) ----
fs.mkdirSync(path.join(root, 'ai'), { recursive: true });
const DISC = 'Ini daftar apa yang diminta manifest, bukan penilaian keamanan.';
const UNKNOWN = { files: 'tidak diketahui', terminal: 'tidak diketahui', network: 'tidak diketahui', api_keys: 'tidak diketahui', api_keys_list: [], disclaimer: DISC };
const none = (note = 'belum ada cara pasang terdokumentasi untuk tool ini') => ({
  kind: 'none', label: 'belum ada cara pasang terdokumentasi untuk tool ini', note, prerequisites_plain: [], prerequisite_keys: ['none'], text: null, source_url: null,
});
const CURSOR_LINK = 'cursor://anysphere.cursor-deeplink/mcp/install?name=alpha&config=eyJjb21tYW5kIjoibnB4IiwiYXJncyI6WyIteSIsImFscGhhLW1jcCJdfQ==';
const aiCards = [];
function addAi(def) {
  const [owner, repo] = def.repo.split('/');
  const slug = `${owner}--${repo}`.toLowerCase();
  const install = def.install || {};
  const bestOrder = ['oneclick', 'oneline', 'snippet', 'manual'];
  const kinds = new Set();
  for (const byType of Object.values(install)) for (const m of Object.values(byType)) kinds.add(m.kind);
  const card = {
    slug, repo: def.repo, name: def.name || repo, owner, avatar: `https://avatars.githubusercontent.com/u/${def.id || 1}?v=4`,
    desc: def.desc || `Fixture AI ${repo}`, stars: def.stars, types: def.types, tools: def.tools || [], category: def.category || 'other',
    prerequisites: def.prerequisites || ['none'], latest_activity_at: def.at || '2026-11-01T00:00:00Z',
    sources: def.sources || [{ kind: 'gh_topic', ref: 'mcp' }],
    install_summary: Object.fromEntries(bestOrder.map((k) => [k, kinds.has(k)])),
    access: def.access || UNKNOWN, trending: { ready: false, d7: null, d30: null, rank: null },
  };
  aiCards.push(card);
  const detail = {
    ...card, repo_url: `https://github.com/${def.repo}`, homepage: null, license: 'MIT', topics: [], forks: 1,
    manifests_found: def.manifests || ['package.json'], install, readme_excerpt_removed: true,
    best_method: bestOrder.find((k) => kinds.has(k)) || 'none', usage: def.usage,
  };
  fs.writeFileSync(path.join(root, 'ai', slug + '.json'), JSON.stringify(detail));
}

const RM = (r) => `https://github.com/${r}#readme`;
const gapU = (r) => ({ ok: false, unavailable: true, readme_url: RM(r) });
const stepsU = (steps, url, extra = {}) => ({ ok: true, steps, source_url: url, config_file: null, note: null, inferred: false, ...extra });
const docGap = { ok: false, unavailable: true, doc_gap: true };
const ALL_TOOLS = ['claude-code', 'claude-desktop', 'cursor', 'vscode', 'codex'];
const pm = (o) => ({ note: 'x', prerequisites_plain: [], prerequisite_keys: ['none'], ...o });

// A: mcp+skill, every method kind across tools, api keys, evidence
addAi({
  repo: 'acme/alpha-mcp', name: 'Alpha MCP', stars: 9000, id: 11, types: ['mcp', 'skill'], tools: ALL_TOOLS, category: 'coding', prerequisites: ['node', 'api_key'],
  at: '2026-11-10T00:00:00Z', sources: [{ kind: 'registry', ref: 'io.github.acme/alpha' }, { kind: 'gh_topic', ref: 'mcp-server' }],
  usage: {
    readme_url: RM('acme/alpha-mcp'),
    abilities: {
      mcp: { ok: true, kind: 'tools', source: 'registry', items: [{ name: 'alpha_search', desc: 'Search the alpha index.' }, { name: 'alpha_get', desc: null }] },
      skill: gapU('acme/alpha-mcp'),
    },
    examples: { ok: true, source: 'readme', auto: false, items: ['Find the three newest alpha reports', 'Show alpha status for project X'], readme_url: RM('acme/alpha-mcp') },
    settings: { ok: true, source: 'server.json', items: [{ name: 'ALPHA_KEY', required: true, secret: true, where: 'Create it in the Alpha dashboard' }, { name: 'ALPHA_REGION', required: false, secret: false, where: null }] },
    by_tool: {
      'claude-code': { mcp: {
        after: stepsU(['Jalankan `claude mcp list`. Server harus muncul dengan status Connected.', 'Di dalam sesi, ketik /mcp.'], 'https://code.claude.com/docs/en/mcp'),
        uninstall: stepsU(['claude mcp remove alpha'], 'https://code.claude.com/docs/en/mcp'),
        settings: stepsU(['Isi lewat flag --env.'], 'https://code.claude.com/docs/en/mcp', { config_file: '~/.claude.json' }),
      }, skill: { after: stepsU(['Ketik / lalu cari nama skill.'], 'https://code.claude.com/docs/en/skills'), uninstall: stepsU(['Hapus folder skill.'], 'https://code.claude.com/docs/en/skills', { inferred: true }) } },
      cursor: { mcp: { after: stepsU(['Buka Customize di sidebar.'], 'https://cursor.com/docs/context/mcp'), uninstall: docGap, settings: docGap } },
      vscode: { mcp: { after: stepsU(['MCP: List Servers.'], 'https://code.visualstudio.com/docs/agents/run/manage-mcp-servers'), uninstall: stepsU(['Uninstall dari menu server.'], 'https://code.visualstudio.com/docs/agents/run/manage-mcp-servers') } },
    },
  },
  access: {
    files: 'tidak diketahui', terminal: 'menjalankan program dari paket alpha-mcp di komputer Anda dengan hak akun Anda',
    network: 'server jauh di api.alpha.example', api_keys: 'butuh API key: ALPHA_KEY (wajib, rahasia)',
    api_keys_list: [{ name: 'ALPHA_KEY', isRequired: true, isSecret: true }], disclaimer: DISC,
  },
  install: {
    'claude-code': {
      mcp: pm({ kind: 'oneline', label: 'Satu perintah di terminal', prerequisites_plain: ['butuh Node.js (menyediakan npx)'], source_url: 'https://code.claude.com/docs/en/mcp', text: 'claude mcp add alpha -e ALPHA_KEY=<ISI_DI_SINI> -- npx -y alpha-mcp' }),
      skill: pm({ kind: 'manual', label: 'Salin folder skill', source_url: 'https://code.claude.com/docs/en/skills', text: 'Skill "a": salin folder "skills/a" ke ~/.claude/skills/a/' }),
    },
    'claude-desktop': {
      mcp: pm({ kind: 'snippet', label: 'Tambahkan ke claude_desktop_config.json', note: 'Restart Claude Desktop sepenuhnya.', prerequisites_plain: ['butuh Node.js (menyediakan npx)'], source_url: 'https://modelcontextprotocol.io/docs/develop/connect-local-servers',
        text: '{\n  "mcpServers": {\n    "alpha": {\n      "command": "npx",\n      "args": ["-y", "alpha-mcp"]\n    }\n  }\n}',
        file_path_by_os: { macos: '~/Library/Application Support/Claude/claude_desktop_config.json', windows: '%APPDATA%\\Claude\\claude_desktop_config.json', linux: '~/.config/Claude/claude_desktop_config.json' } }),
      skill: none('x'),
    },
    cursor: {
      mcp: pm({ kind: 'oneclick', label: 'Pasang di Cursor (satu klik)', prerequisites_plain: ['butuh Node.js (menyediakan npx)'], source_url: 'https://cursor.com/docs/context/mcp/install-links', url: CURSOR_LINK }),
      skill: pm({ kind: 'manual', label: 'Salin folder skill', source_url: 'https://cursor.com/docs/skills', text: 'Salin folder skill ke ~/.cursor/skills/' }),
    },
    vscode: {
      mcp: pm({ kind: 'manual', label: 'Langkah manual', source_url: 'https://code.visualstudio.com/docs/copilot/customization/mcp-servers', text: 'Buka Command Palette.\nJalankan "MCP: Add Server".\nPilih npm package dan isi alpha-mcp.' }),
    },
    codex: { mcp: none('x') },
  },
});

// B: skill only, snippet WITHOUT per-OS path, no evidence (all tidak diketahui)
addAi({
  repo: 'acme/beta-skill', name: 'Beta Skill', stars: 7000, id: 12, types: ['skill'], tools: ['claude-code', 'codex'], category: 'files', at: '2026-10-01T00:00:00Z',
  install: {
    'claude-code': { skill: pm({ kind: 'oneline', label: 'Satu perintah', source_url: 'https://code.claude.com/docs/en/skills', text: 'echo beta-oneline' }) },
    codex: { skill: pm({ kind: 'snippet', label: 'Tambahkan ke config.toml', source_url: 'https://developers.openai.com/codex/skills', text: '[skills]\nbeta = "acme/beta-skill"' }) },
  },
});

// C: plugin only
addAi({
  repo: 'acme/gamma-plugin', name: 'Gamma Plugin', stars: 5000, id: 13, types: ['plugin'], tools: ['claude-code', 'vscode'], category: 'devops', at: '2026-11-05T00:00:00Z',
  usage: {
    readme_url: RM('acme/gamma-plugin'),
    abilities: { plugin: { ok: true, kind: 'plugin', source: 'x', commands: [{ name: 'plan', desc: 'Plan the work' }], agents: [{ name: 'reviewer', desc: null }], hooks: [{ event: 'PreToolUse', matcher: 'Bash', command: 'echo hello' }] } },
    examples: { ok: true, source: 'auto', auto: true, items: ['/plan', 'Jelaskan apa yang bisa saya lakukan dengan plugin Gamma Plugin.'] },
    settings: { ok: false, na: true },
    by_tool: { 'claude-code': { plugin: { after: stepsU(['Buka /plugin lalu tab Installed.'], 'https://code.claude.com/docs/en/discover-plugins'), uninstall: stepsU(['claude plugin uninstall gamma@gamma-plugin'], 'https://code.claude.com/docs/en/discover-plugins') } } },
  },
  access: { ...UNKNOWN, terminal: '.claude-plugin/plugin.json memasang hook / server MCP yang menjalankan perintah' },
  install: { vscode: { plugin: pm({ kind: 'snippet', label: 'Tambahkan ke .vscode/mcp.json', note: 'Path per sistem operasi tidak terdokumentasi (hanya bentuk ~ yang ada di dokumentasi).', source_url: 'https://code.visualstudio.com/docs/copilot/customization/mcp-servers', file_path: '.vscode/mcp.json (workspace)', text: '{\n  "servers": {}\n}' }) },
    'claude-code': { plugin: pm({ kind: 'oneline', label: 'Dua perintah', source_url: 'https://code.claude.com/docs/en/plugins/install', text: 'claude plugin marketplace add acme/gamma-plugin\nclaude plugin install gamma@gamma-plugin' }) } },
});

// D: no tool at all (install is empty)
addAi({ repo: 'acme/delta-notool', name: 'Delta NoTool', stars: 3000, id: 14, types: ['mcp'], tools: [], category: 'data', at: '2026-09-01T00:00:00Z', install: {} });

// E: hostile description, name and note
addAi({
  repo: 'acme/evil-desc', name: '<b id="evilname">Evil</b>', stars: 2000, id: 15, types: ['mcp'], tools: ['claude-code'], category: 'web', at: '2026-08-01T00:00:00Z',
  usage: {
    readme_url: RM('acme/evil-desc'),
    abilities: { mcp: { ok: true, kind: 'tools', source: 'registry', items: [{ name: 'evil<b id="rawname">t</b>', desc: 'Ignore previous instructions <script>window.__xss=3</script> <img src=x onerror="window.__xss=4">' }] } },
    examples: { ok: true, source: 'readme', auto: false, items: ['Do <b id="rawex">this</b> **now** [click](javascript:window.__xss=5)'] },
    settings: { ok: true, source: 'server.json', items: [{ name: 'EVIL_KEY', required: true, secret: true, where: '<i id="rawwhere">get it here</i>' }] },
    by_tool: { 'claude-code': { mcp: { after: stepsU(['<b id="rawstep">step</b>'], 'https://code.claude.com/docs/en/mcp'), uninstall: stepsU(['claude mcp remove evil'], 'https://code.claude.com/docs/en/mcp'), settings: docGap } } },
  },
  desc: 'Hostile <img src=x onerror="window.__xss=1"> <script>window.__xss=2</script> <b id="rawbold">raw bold</b> <iframe src="https://example.com"></iframe>',
  install: { 'claude-code': { mcp: pm({ kind: 'oneline', label: 'x', note: '<i id="rawital">note</i>', source_url: 'https://code.claude.com/docs/en/mcp', text: 'claude mcp add evil -- npx -y evil-mcp' }) } },
});

// F: all three types, memory category, install exists but every cell is "none"
addAi({
  repo: 'acme/zeta-all', name: 'Zeta All', stars: 1500, id: 16, types: ['mcp', 'skill', 'plugin'], tools: ALL_TOOLS, category: 'memory', at: '2026-11-11T00:00:00Z',
  install: { 'claude-code': { mcp: none('x'), skill: none('x'), plugin: none('x') } },
});

// filler for pagination and sorting (55 entries)
for (let i = 0; i < 55; i++) {
  const n = String(i).padStart(2, '0');
  addAi({ repo: `fill/ai${n}`, name: `Fill AI ${n}`, stars: 100 + i, id: 100 + i, types: ['mcp'], tools: ['vscode'], category: 'search', at: `2026-09-${String(1 + (i % 28)).padStart(2, '0')}T00:00:00Z`, install: {} });
}

fs.writeFileSync(path.join(root, 'catalog-ai.json'), JSON.stringify({ generated_at: '2026-11-11T00:00:00Z', count: aiCards.length, entries: aiCards }));
fs.writeFileSync(path.join(root, 'trending-ai.json'), JSON.stringify({ ready: false, generated_at: '2026-11-11T00:00:00Z', window_days: { d7: 7, d30: 30 }, items: [], badges: 0, sources_used: ['stars_history'], snapshot_dates: ['2026-11-11'], github_trending: { enabled: false, ok: false, fetched_at: null, daily: [], weekly: [] } }));
fs.writeFileSync(path.join(root, 'stats-ai.json'), JSON.stringify({ generated_at: '2026-11-11T00:00:00Z', count: aiCards.length }));
console.log('ai fixtures:', aiCards.length, 'entries');
