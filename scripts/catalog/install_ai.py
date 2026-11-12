"""Install text + 'Yang bisa diakses' box (SPEC_AI.md sections 2-3). Deterministic, from manifest fields only.
Only cells of the matrix in site/research/install_methods.md produce a method; every method carries that file's source_url.
Everything else is kind 'none'. The words for 'safe' (Indonesian and English) are never produced here; the fixed sentence
DISCLAIMER says it is not a safety assessment without containing either word."""
import re, json, base64, urllib.parse

TOOLS = ['claude-code', 'claude-desktop', 'cursor', 'vscode', 'codex']
KINDS = ['oneclick', 'oneline', 'snippet', 'manual']      # best first
PH = '<ISI_DI_SINI>'
NONE_TEXT = 'belum ada cara pasang terdokumentasi untuk tool ini'
DISCLAIMER = 'Ini daftar apa yang diminta manifest, bukan penilaian keamanan.'
UNKNOWN = 'tidak diketahui'

SRC = {
    ('claude-code', 'mcp'): 'https://code.claude.com/docs/en/mcp',
    ('claude-code', 'skill'): 'https://code.claude.com/docs/en/skills',
    ('claude-code', 'plugin'): 'https://code.claude.com/docs/en/plugins/install',
    ('claude-desktop', 'mcp'): 'https://modelcontextprotocol.io/docs/develop/connect-local-servers',
    ('claude-desktop', 'mcp_remote'): 'https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp',
    ('claude-desktop', 'skill'): 'https://support.claude.com/en/articles/12512180-using-skills-in-claude',
    ('cursor', 'mcp'): 'https://cursor.com/docs/context/mcp',
    ('cursor', 'mcp_deeplink'): 'https://cursor.com/docs/context/mcp/install-links',
    ('cursor', 'skill'): 'https://cursor.com/docs/skills',
    ('vscode', 'mcp'): 'https://code.visualstudio.com/docs/copilot/reference/mcp-configuration',
    ('vscode', 'mcp_snippet'): 'https://code.visualstudio.com/docs/copilot/customization/mcp-servers',
    ('vscode', 'skill'): 'https://code.visualstudio.com/docs/copilot/customization/agent-skills',
    ('vscode', 'plugin'): 'https://code.visualstudio.com/docs/copilot/customization/agent-plugins',
    ('codex', 'mcp'): 'https://learn.chatgpt.com/docs/extend/mcp?surface=cli',
    ('codex', 'mcp_remote'): 'https://learn.chatgpt.com/docs/extend/mcp?surface=ide',
    ('codex', 'skill'): 'https://learn.chatgpt.com/docs/build-skills',
    ('codex', 'plugin'): 'https://learn.chatgpt.com/docs/plugins',
}
CLAUDE_DESKTOP_PATHS = {
    'macos': '~/Library/Application Support/Claude/claude_desktop_config.json',
    'windows': '%APPDATA%\\Claude\\claude_desktop_config.json',
    'linux': '~/.config/Claude/claude_desktop_config.json',
}
SKILL_TARGET = {
    'claude-code': '~/.claude/skills/',
    'cursor': '~/.cursor/skills/',
    'vscode': '~/.copilot/skills/',
    'codex': '$HOME/.agents/skills/',
}
NO_OS_PATH = 'Path per sistem operasi tidak terdokumentasi (hanya bentuk ~ yang ada di dokumentasi).'


# ------------------------------------------------------------------ helpers
def posix_quote(s):
    s = str(s)
    if s == PH or re.match(r'^[A-Za-z0-9_@%+=:,./-]+$', s): return s
    return "'" + s.replace("'", "'\\''") + "'"


def server_name(raw, fallback='server'):
    n = str(raw or '').split('/')[-1].lower()
    n = re.sub(r'[^a-z0-9_-]+', '-', n).strip('-_')
    return n[:40] or fallback


def cursor_deeplink(name, config):
    """cursor://anysphere.cursor-deeplink/mcp/install?name=NAME&config=BASE64(JSON.stringify(config)); config = bare server object."""
    raw = json.dumps(config, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    b64 = base64.b64encode(raw).decode('ascii')
    return 'cursor://anysphere.cursor-deeplink/mcp/install?name=%s&config=%s' % (
        urllib.parse.quote(name, safe=''), urllib.parse.quote(b64, safe='='))


def decode_cursor_deeplink(url):
    """Inverse of cursor_deeplink (used by tests): -> (name, config dict)."""
    u = urllib.parse.urlsplit(url)
    assert u.scheme == 'cursor' and u.netloc == 'anysphere.cursor-deeplink' and u.path == '/mcp/install', url
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    return q['name'][0], json.loads(base64.b64decode(q['config'][0]).decode('utf-8'))


def vscode_plugin_deeplink(source, plugin):
    return 'vscode://chat-plugin/install?source=%s&plugin=%s' % (urllib.parse.quote(source, safe=''), urllib.parse.quote(plugin, safe=''))


# ------------------------------------------------------------------ launch spec (MCP)
def _is_template(s): return isinstance(s, str) and '{' in s and '}' in s


def _pkg_args(p):
    out, need = [], False
    for a in p.get('packageArguments') or []:
        if not isinstance(a, dict): continue
        val = a.get('value', a.get('default'))
        req = bool(a.get('isRequired'))
        if val is None or _is_template(val):
            if not req: continue
            val, need = PH, True
        if a.get('type') == 'named' and a.get('name'):
            out += [str(a['name']), str(val)]
        elif a.get('type') in ('positional', None):
            out.append(str(val))
    return out, need


RUNTIME_ARGS_NOTE = 'server.json memakai runtimeArguments; urutan argumennya belum terverifikasi, jadi tidak ada tombol pasang'


def _has_runtime_args(p):
    ra = p.get('runtimeArguments') or []
    # Narrow exception (decided after a real install test): an npm package whose ONLY runtime argument is the
    # positional "-y" is redundant (the generator already emits `npx -y`), so there is no ordering question.
    # Verified working: `npx -y repomix --mcp` (Claude Code, Codex handshake). Everything else stays blocked.
    if (p.get('registryType') == 'npm' and len(ra) == 1 and ra[0].get('type') == 'positional'
            and str(ra[0].get('value', ra[0].get('valueHint', ''))).strip() == '-y'):
        return False
    return bool(ra)


def _env(p):
    env = {}
    for e in p.get('environmentVariables') or []:
        if not isinstance(e, dict) or not e.get('name') or not e.get('isRequired'): continue
        v = e.get('value', e.get('default'))
        env[e['name']] = PH if (v is None or _is_template(v)) else str(v)
    return env


def server_dict(M):
    return M.get('registry_server') or M.get('server_json')


def launch_spec(M):
    """-> dict or None. Priority: stdio npm, stdio pypi, remote streamable-http. None if no documented/derivable launch.
    The repo's own package.json/pyproject name is NOT used (it may be unpublished or squatted)."""
    sd = server_dict(M)
    if not sd: return None
    pk = [p for p in sd.get('packages') or [] if isinstance(p, dict) and isinstance(p.get('identifier'), str)
          and str((p.get('transport') or {}).get('type', 'stdio')).lower() == 'stdio']
    blocked = None
    for rt, cmd in (('npm', 'npx'), ('pypi', 'uvx')):
        for p in pk:
            if str(p.get('registryType', '')).lower() == rt:
                if _has_runtime_args(p):      # order/semantics vs. package id unverified -> no command at all
                    blocked = blocked or {'kind': 'blocked', 'reason': RUNTIME_ARGS_NOTE, 'package': p['identifier']}
                    continue
                a, need = _pkg_args(p)
                base = ['-y', p['identifier']] if rt == 'npm' else [p['identifier']]
                return {'kind': 'stdio', 'registry': rt, 'command': cmd, 'args': base + a, 'env': _env(p),
                        'package': p['identifier'], 'arg_placeholder': need}
    for r in sd.get('remotes') or []:
        if not isinstance(r, dict) or not isinstance(r.get('url'), str): continue
        if str(r.get('type', '')).lower() != 'streamable-http': continue
        hdrs = [h for h in r.get('headers') or [] if isinstance(h, dict) and h.get('isRequired')]
        if _is_template(r['url']) and not r.get('variables'): continue
        return {'kind': 'remote', 'url': r['url'], 'needs_headers': bool(hdrs) or _is_template(r['url']),
                'headers': {h.get('name'): PH for h in hdrs if h.get('name')}}
    return blocked


def stdio_config(sp):
    c = {'command': sp['command'], 'args': list(sp['args'])}
    if sp['env']: c['env'] = dict(sp['env'])
    return c


# ------------------------------------------------------------------ prerequisites (plain Indonesian)
def prereq_plain(sp):
    out, keys = [], []
    if sp and sp['kind'] == 'stdio':
        if sp['command'] == 'npx': out.append('butuh Node.js (menyediakan npx)'); keys.append('node')
        else: out.append('butuh uv (menyediakan uvx)'); keys.append('uv')
        for k, v in sp['env'].items():
            if v == PH: out.append('butuh API key: %s (ganti %s)' % (k, PH)); keys.append('api_key')
        if sp.get('arg_placeholder'): out.append('ada argumen wajib: ganti %s dengan nilai Anda' % PH)
    if sp and sp['kind'] == 'remote':
        for k in sp.get('headers') or {}:
            out.append('butuh API key: %s (ganti %s)' % (k, PH)); keys.append('api_key')
    return out, keys


def _m(kind, label, source_url, prereq, keys, note='', text=None, url=None, file_path=None, file_path_by_os=None):
    d = {'kind': kind, 'label': label, 'note': note, 'prerequisites_plain': prereq, 'prerequisite_keys': keys or ['none'],
         'source_url': source_url}
    if text is not None: d['text'] = text
    if url is not None: d['url'] = url
    if file_path: d['file_path'] = file_path
    if file_path_by_os: d['file_path_by_os'] = file_path_by_os
    return d


def _none(tool, type_key, why=''):
    return {'kind': 'none', 'label': NONE_TEXT, 'note': why or NONE_TEXT, 'prerequisites_plain': [], 'prerequisite_keys': ['none'],
            'text': None, 'source_url': None}


# ------------------------------------------------------------------ MCP
def mcp_install(tool, name, sp):
    if sp and sp['kind'] == 'blocked': return _none(tool, 'mcp', sp['reason'])
    if not sp: return _none(tool, 'mcp', 'manifest tidak memuat paket npm/pypi atau remote streamable-http yang bisa dipakai')
    pre, keys = prereq_plain(sp)
    if sp['kind'] == 'stdio':
        cfg = stdio_config(sp)
        envs = ' '.join('-e %s=%s' % (k, posix_quote(v)) for k, v in sp['env'].items())
        cmdline = ' '.join([sp['command']] + [posix_quote(a) for a in sp['args']])
        if tool == 'claude-code':
            return _m('oneline', 'Satu perintah di terminal', SRC[(tool, 'mcp')], pre, keys,
                      'Cakupan bawaan: local. Tambah -s user atau -s project bila perlu.',
                      text='claude mcp add %s%s -- %s' % (name, (' ' + envs) if envs else '', cmdline))
        if tool == 'claude-desktop':
            snip = json.dumps({'mcpServers': {name: cfg}}, indent=2, ensure_ascii=False)
            return _m('snippet', 'Tambahkan ke claude_desktop_config.json', SRC[(tool, 'mcp')], pre, keys,
                      'Buka Settings > Developer > Edit Config, tempel, lalu restart Claude Desktop sepenuhnya. Di Windows, backslash di dalam JSON harus di-escape.',
                      text=snip, file_path_by_os=dict(CLAUDE_DESKTOP_PATHS))
        if tool == 'cursor':
            if sp['command'] == 'npx':
                return _m('oneclick', 'Pasang di Cursor (satu klik)', SRC[(tool, 'mcp_deeplink')], pre, keys,
                          'Cursor meminta persetujuan sebelum memakai tool MCP.' + (' Ganti %s di pengaturan MCP Cursor setelah terpasang.' % PH if keys.count('api_key') or sp.get('arg_placeholder') else ''),
                          url=cursor_deeplink(name, cfg))
            snip = json.dumps({'mcpServers': {name: cfg}}, indent=2, ensure_ascii=False)
            return _m('snippet', 'Tambahkan ke .cursor/mcp.json', SRC[(tool, 'mcp')], pre, keys, NO_OS_PATH,
                      text=snip, file_path='.cursor/mcp.json (proyek) atau ~/.cursor/mcp.json (global)')
        if tool == 'vscode':
            js = json.dumps(dict([('name', name), ('type', 'stdio')] + list(cfg.items())), separators=(',', ':'), ensure_ascii=False)
            if "'" not in js:
                return _m('oneline', 'Satu perintah di terminal', SRC[(tool, 'mcp')], pre, keys,
                          'Menambah ke mcp.json profil pengguna. Aturan tanda kutip berbeda per shell; contoh ini untuk shell bergaya POSIX.',
                          text="code --add-mcp '%s'" % js)
            snip = json.dumps({'servers': {name: dict([('type', 'stdio')] + list(cfg.items()))}}, indent=2, ensure_ascii=False)
            return _m('snippet', 'Tambahkan ke .vscode/mcp.json', SRC[(tool, 'mcp_snippet')], pre, keys, NO_OS_PATH,
                      text=snip, file_path='.vscode/mcp.json (workspace)')
        if tool == 'codex':
            return _m('oneline', 'Satu perintah di terminal', SRC[(tool, 'mcp')], pre, keys,
                      'Restart Codex setelah menambah server.',
                      text='codex mcp add %s%s -- %s' % (name, (' ' + envs.replace('-e ', '--env ')) if envs else '', cmdline))
    else:  # remote
        url = sp['url']
        if sp['needs_headers']:
            hdr = sp.get('headers') or {}
            if tool == 'cursor':
                c = {'url': url}
                if hdr: c['headers'] = hdr
                return _m('snippet', 'Tambahkan ke .cursor/mcp.json', SRC[(tool, 'mcp')], pre, keys, NO_OS_PATH,
                          text=json.dumps({'mcpServers': {name: c}}, indent=2), file_path='.cursor/mcp.json (proyek) atau ~/.cursor/mcp.json (global)')
            if tool == 'vscode':
                c = {'type': 'http', 'url': url}
                if hdr: c['headers'] = hdr
                return _m('snippet', 'Tambahkan ke .vscode/mcp.json', SRC[(tool, 'mcp_snippet')], pre, keys, NO_OS_PATH,
                          text=json.dumps({'servers': {name: c}}, indent=2), file_path='.vscode/mcp.json (workspace)')
            return _none(tool, 'mcp', 'server jauh ini butuh header/variabel; tidak ada cara terdokumentasi untuk tool ini')
        if tool == 'claude-code':
            return _m('oneline', 'Satu perintah di terminal', SRC[(tool, 'mcp')], pre, keys, 'Cakupan bawaan: local.',
                      text='claude mcp add --transport http %s %s' % (name, posix_quote(url)))
        if tool == 'claude-desktop':
            return _m('manual', 'Langkah di aplikasi', SRC[(tool, 'mcp_remote')], pre, keys,
                      'Berjalan dari cloud Anthropic, bukan dari komputer Anda.',
                      text='Buka Customize > Connectors > + Add > Add custom connector, lalu isi URL: %s' % url)
        if tool == 'cursor':
            return _m('snippet', 'Tambahkan ke .cursor/mcp.json', SRC[(tool, 'mcp')], pre, keys, NO_OS_PATH,
                      text=json.dumps({'mcpServers': {name: {'url': url}}}, indent=2), file_path='.cursor/mcp.json (proyek) atau ~/.cursor/mcp.json (global)')
        if tool == 'vscode':
            js = json.dumps({'name': name, 'type': 'http', 'url': url}, separators=(',', ':'))
            return _m('oneline', 'Satu perintah di terminal', SRC[(tool, 'mcp')], pre, keys,
                      'Menambah ke mcp.json profil pengguna. Aturan tanda kutip berbeda per shell.',
                      text="code --add-mcp '%s'" % js)
        if tool == 'codex':
            return _m('oneline', 'Satu perintah di terminal', SRC[(tool, 'mcp_remote')], pre, keys, 'Restart Codex setelah menambah server.',
                      text='codex mcp add %s --url %s' % (name, posix_quote(url)))
    return _none(tool, 'mcp')


# ------------------------------------------------------------------ skill
def skill_install(tool, repo, skills):
    if not skills: return _none(tool, 'skill')
    url = 'https://github.com/%s' % repo
    lines = []
    for s in skills[:5]:
        src = ('folder "%s"' % s['dir']) if s['dir'] else 'akar repo'
        if tool == 'claude-desktop':
            lines.append('Skill "%s": unduh %s dari %s, jadikan ZIP.' % (s['name'], src, url))
        else:
            lines.append('Skill "%s": salin %s dari %s ke %s%s/' % (s['name'], src, url, SKILL_TARGET[tool], s['name']))
    if tool == 'claude-desktop':
        lines.append('Lalu: Customize > Skills > + Create skill > Upload a skill.')
        note = 'Direktori skill dan perintah untuk Claude Desktop tidak terdokumentasi; hanya unggah ZIP lewat UI.'
    elif tool == 'claude-code':
        note = 'Tidak ada perintah install (salin folder). Folder skill baru butuh /reload-skills.'
    elif tool == 'cursor':
        note = 'Nama skill harus sama dengan nama folder. Perintah install tidak terdokumentasi.'
    elif tool == 'codex':
        note = 'Perintah `codex skills install` tidak terdokumentasi; salin folder saja.'
    else:
        note = 'Perintah install lewat CLI tidak terdokumentasi; salin folder saja.'
    return _m('manual', 'Salin folder skill', SRC[(tool, 'skill')], [], ['none'], note, text='\n'.join(lines))


# ------------------------------------------------------------------ plugin
def _plugin_names(mk):
    return [p['name'] for p in (mk.get('plugins') or []) if isinstance(p, dict) and isinstance(p.get('name'), str) and p['name']]


def plugin_install(tool, repo, M):
    mk = (M.get('marketplaces') or {})
    cc_mk = mk.get('.claude-plugin/marketplace.json')
    hook_note = 'Plugin bisa menjalankan hook dan server MCP dengan hak akun Anda.'
    if tool == 'claude-code' and cc_mk:
        names = _plugin_names(cc_mk)
        if isinstance(cc_mk.get('name'), str) and cc_mk['name'] and names:
            return _m('oneline', 'Dua perintah di terminal', SRC[(tool, 'plugin')], [], ['none'], hook_note,
                      text='claude plugin marketplace add %s\nclaude plugin install %s@%s' % (repo, names[0], cc_mk['name']))
    if tool == 'vscode':
        claude_plugin = (M.get('plugins') or {}).get('.claude-plugin/plugin.json') or (M.get('plugins') or {}).get('plugin.json') or cc_mk
        if claude_plugin:
            nm = claude_plugin.get('name') if isinstance(claude_plugin.get('name'), str) and claude_plugin.get('name') and 'plugins' not in claude_plugin else None
            nm = nm or (_plugin_names(claude_plugin) or [repo.split('/')[-1]])[0]
            return _m('oneclick', 'Pasang lewat VS Code', SRC[(tool, 'plugin')],
                      ['butuh setting chat.plugins.enabled (Experimental) di VS Code'], ['none'],
                      'VS Code selalu minta konfirmasi. ' + hook_note,
                      url=vscode_plugin_deeplink('https://github.com/%s' % repo, nm))
    if tool == 'codex' and '.agents/plugins/marketplace.json' in mk:
        return _m('oneline', 'Satu perintah di terminal', SRC[(tool, 'plugin')], [], ['none'],
                  'Lalu buka /plugins di Codex. Tidak untuk ekstensi IDE. ' + hook_note,
                  text='codex plugin marketplace add %s' % repo)
    return _none(tool, 'plugin')


# ------------------------------------------------------------------ whole entry
def install_name(M, repo):
    """The server name used in every MCP install command (uninstall commands must use the same one)."""
    name = server_name((server_dict(M) or {}).get('name') if server_dict(M) else None, repo.split('/')[-1].lower())
    if name == 'server' or not name: name = server_name(repo.split('/')[-1])
    return name


def build_install(M, repo, types):
    """-> (install{tool:{type:method}}, tools[], prerequisites[], methods_flat)."""
    sp = launch_spec(M) if 'mcp' in types else None
    name = install_name(M, repo)
    inst, tools, prereq = {}, [], []
    for tool in TOOLS:
        cell = {}
        for t in types:
            if t == 'mcp': cell[t] = mcp_install(tool, name, sp)
            elif t == 'skill':
                cell[t] = skill_install(tool, repo, M.get('skills') or []) if tool in SKILL_TARGET or tool == 'claude-desktop' else _none(tool, t)
            elif t == 'plugin': cell[t] = plugin_install(tool, repo, M)
        inst[tool] = cell
        if any(v['kind'] != 'none' for v in cell.values()): tools.append(tool)
        for v in cell.values():
            if v['kind'] != 'none':
                for k in v['prerequisite_keys']:
                    if k != 'none' and k not in prereq: prereq.append(k)
    return inst, tools, prereq or ['none']


def summarize(install):
    flags = {k: False for k in KINDS}
    for cell in install.values():
        for v in cell.values():
            if v['kind'] in flags: flags[v['kind']] = True
    best = next((k for k in KINDS if flags[k]), 'none')
    return flags, best


# ------------------------------------------------------------------ access box
FILE_TOOLS = {'Read', 'Write', 'Edit'}


def _host(u):
    return urllib.parse.urlsplit(u).hostname or u


def access_box(M, types, from_registry=False):
    sd = server_dict(M) or {}
    terminal, network, files, keys = [], [], [], []
    hosts = []
    for r in sd.get('remotes') or []:
        if isinstance(r, dict) and isinstance(r.get('url'), str):
            h = _host(r['url'])
            if h not in hosts: hosts.append(h)
    if hosts: network.append('server jauh di %s' % ', '.join(hosts))
    pk_names = []
    for p in sd.get('packages') or []:
        if isinstance(p, dict) and str(p.get('registryType', '')).lower() in ('npm', 'pypi') \
                and str((p.get('transport') or {}).get('type', 'stdio')).lower() == 'stdio' and isinstance(p.get('identifier'), str)                 and not _has_runtime_args(p):      # no command is shown for these, so do not claim it is run
            pk_names.append(p['identifier'])
    if pk_names:
        terminal.append('menjalankan program dari paket %s di komputer Anda dengan hak akun Anda' % ', '.join(pk_names))
    items = []
    for p in sd.get('packages') or []:
        if isinstance(p, dict):
            for e in p.get('environmentVariables') or []:
                if isinstance(e, dict) and e.get('name'):
                    it = {'name': e['name'], 'isRequired': bool(e.get('isRequired')), 'isSecret': bool(e.get('isSecret'))}
                    if it not in items: items.append(it)
    if items:
        keys.append('butuh API key: ' + ', '.join('%s (%s%s)' % (i['name'], 'wajib' if i['isRequired'] else 'opsional', ', rahasia' if i['isSecret'] else '') for i in items))
    for s in M.get('skills') or []:
        at = s.get('allowed_tools')
        if not at: continue
        if 'Bash' in at: terminal.append('skill "%s" meminta tool Bash (allowed-tools)' % s['name'])
        ft = [t for t in at if t in FILE_TOOLS]
        if ft: files.append('skill "%s" meminta tool file: %s (allowed-tools)' % (s['name'], ', '.join(ft)))
    for grp in ('plugins', 'marketplaces'):
        for path, j in (M.get(grp) or {}).items():
            if isinstance(j, dict) and ('hooks' in j or 'mcpServers' in j):
                terminal.append('%s memasang hook / server MCP yang menjalankan perintah' % path)
    def j(x): return '; '.join(x) if x else UNKNOWN
    return {'files': j(files), 'terminal': j(terminal), 'network': j(network), 'api_keys': j(keys), 'api_keys_list': items,
            'disclaimer': DISCLAIMER}
