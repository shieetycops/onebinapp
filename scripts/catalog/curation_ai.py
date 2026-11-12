"""AI-tools curation (SPEC_AI.md section 1): manifest parsing, type detection, rules R1-R8. Pure functions, stdlib only, no network.

Decisions (also reported by build_ai.py):
 * Each repo gets only its FIRST failing code, checked in order R1,R2,R3,R4,R5,R6,R7,R8.
 * R2: a missing release (or missing pushedAt) counts as old.
 * R4: a registry server.json counts as a parsed manifest (path 'registry:server.json').
 * R6 is applied exactly as written (any match rejects), to: README code blocks / inline code (first 20000 chars),
   package.json scripts, plugin/marketplace/server.json strings (commands, hooks, args).
 * R7 is manifest-vs-manifest only (see check_disguised); it is skipped when repository.subfolder is set,
   or the root package.json is private/has workspaces.
 * README is read only from 'HEAD:README.md' (case-sensitive path; repos with another casing have no README text for R6).
"""
import re, json, base64, datetime

try:
    import tomllib
except Exception:  # pragma: no cover
    tomllib = None

MANIFEST_PATHS = ['package.json', 'pyproject.toml', 'server.json', 'plugin.json', '.claude-plugin/plugin.json',
                  '.claude-plugin/marketplace.json', '.codex-plugin/plugin.json', '.cursor-plugin/plugin.json',
                  '.agents/plugins/marketplace.json', 'SKILL.md']
PLUGIN_PATHS = ['plugin.json', '.claude-plugin/plugin.json', '.claude-plugin/marketplace.json', '.codex-plugin/plugin.json',
                '.cursor-plugin/plugin.json', '.agents/plugins/marketplace.json']
README_MAX = 20000
CODES = ['owner_unclear', 'inactive', 'archived_or_disabled', 'no_manifest', 'lifecycle_fetch', 'pipe_to_shell',
         'disguised_install', 'not_ai_tool']
OWNER_MIN_DAYS = 180
ACTIVE_DAYS = 183


def parse_ts(s):
    if not s: return None
    try:
        return datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None


# ------------------------------------------------------------------ parsing
def parse_json(text):
    if not text: return None
    try:
        v = json.loads(text.lstrip('﻿'))
    except Exception:
        return None
    return v if isinstance(v, dict) and v else None


def parse_toml(text):
    if not text or tomllib is None: return None
    try:
        v = tomllib.loads(text)
    except Exception:
        return None
    return v if isinstance(v, dict) and v else None


def _unq(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'': return v[1:-1]
    return v


def parse_frontmatter(text):
    """Minimal YAML-ish frontmatter: 'key: value', block scalars (> | >- |-), '- item' lists. -> dict|None."""
    if not text: return None
    lines = text.lstrip('﻿').replace('\r\n', '\n').split('\n')
    if not lines or lines[0].strip() != '---': return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---': end = i; break
    if end is None: return None
    out, i, body = {}, 0, lines[1:end]
    while i < len(body):
        ln = body[i]
        m = re.match(r'^([A-Za-z0-9_.-]+)\s*:\s*(.*)$', ln)
        if not m or ln.startswith((' ', '\t')):
            i += 1; continue
        k, v = m.group(1), m.group(2).strip()
        i += 1
        if v in ('>', '>-', '|', '|-', '>+', '|+') or v == '':
            blk = []
            while i < len(body) and (body[i].startswith((' ', '\t')) or body[i].strip() == ''):
                blk.append(body[i].strip()); i += 1
            items = [b[1:].strip() for b in blk if b.startswith('- ')]
            if v == '' and items:
                out[k] = [_unq(x) for x in items]
            else:
                out[k] = ' '.join(b for b in blk if b).strip()
        else:
            if v.startswith('[') and v.endswith(']'):
                out[k] = [_unq(x) for x in v[1:-1].split(',') if x.strip()]
            else:
                out[k] = _unq(v)
    return out


def parse_skill(path, text):
    fm = parse_frontmatter(text)
    if not fm: return None
    name, desc = fm.get('name'), fm.get('description')
    if not isinstance(name, str) or not name.strip() or not isinstance(desc, str) or not desc.strip(): return None
    at = fm.get('allowed-tools', fm.get('allowed_tools'))
    if isinstance(at, str):
        at = [x for x in re.split(r'[,\s]+(?![^(]*\))', at) if x]
    tools = []
    for t in at or []:
        base = re.split(r'[(\s]', str(t).strip(), 1)[0]
        if base: tools.append(base)
    d = path.rsplit('/', 1)[0] if '/' in path else ''
    return {'path': path, 'dir': d, 'name': name.strip(), 'description': desc.strip(), 'allowed_tools': tools if at else None}


def parse_manifests(texts, registry_server=None, skill_files=None):
    """texts: path -> text|None for MANIFEST_PATHS. skill_files: nested SKILL.md path -> text. -> M dict."""
    M = {'found': [], 'package_json': None, 'pyproject': None, 'server_json': None, 'registry_server': None,
         'plugins': {}, 'marketplaces': {}, 'skills': []}
    t = texts or {}
    pj = parse_json(t.get('package.json'))
    if pj: M['package_json'] = pj; M['found'].append('package.json')
    pp = parse_toml(t.get('pyproject.toml'))
    if pp: M['pyproject'] = pp; M['found'].append('pyproject.toml')
    sj = parse_json(t.get('server.json'))
    if sj: M['server_json'] = sj; M['found'].append('server.json')
    if registry_server: M['registry_server'] = registry_server; M['found'].append('registry:server.json')
    for p in PLUGIN_PATHS:
        j = parse_json(t.get(p))
        if j:
            (M['marketplaces'] if p.endswith('marketplace.json') else M['plugins'])[p] = j
            M['found'].append(p)
    allsk = []
    if t.get('SKILL.md'): allsk.append(('SKILL.md', t['SKILL.md']))
    allsk += sorted((skill_files or {}).items())
    for p, txt in allsk:
        s = parse_skill(p, txt)
        if s:
            M['skills'].append(s); M['found'].append(p)
    M['skills'] = M['skills'][:5]
    return M


# ------------------------------------------------------------------ types
MCP_NPM_DEPS = ('@modelcontextprotocol/sdk', 'fastmcp', 'mcp')


def _req_name(r):
    m = re.match(r'^\s*([A-Za-z0-9_.-]+)', str(r))
    return m.group(1).lower().replace('_', '-') if m else ''


def _is_mcp_name(n):
    return n in ('mcp', 'fastmcp') or n.startswith('mcp-server-') or n.startswith('@modelcontextprotocol/')


def has_mcp_dependency(M):
    pj = M.get('package_json') or {}
    for k in ('dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'):
        d = pj.get(k)
        if isinstance(d, dict):
            for n in d:
                n = n.lower()
                if n in MCP_NPM_DEPS or n.startswith('mcp-server-') or n == '@modelcontextprotocol/sdk': return True
    pp = M.get('pyproject') or {}
    proj = pp.get('project') or {}
    reqs = list(proj.get('dependencies') or [])
    for v in (proj.get('optional-dependencies') or {}).values(): reqs += list(v or [])
    for g in (pp.get('dependency-groups') or {}).values():
        reqs += [x for x in (g or []) if isinstance(x, str)]
    poetry = ((pp.get('tool') or {}).get('poetry') or {})
    reqs += list((poetry.get('dependencies') or {}).keys())
    return any(_is_mcp_name(_req_name(r)) for r in reqs if isinstance(r, str))


def detect_types(M, from_registry=False):
    types = []
    if M.get('server_json') or M.get('registry_server') or from_registry or has_mcp_dependency(M): types.append('mcp')
    if M.get('skills'): types.append('skill')
    if M.get('plugins') or M.get('marketplaces'): types.append('plugin')
    return types


# ------------------------------------------------------------------ R5
FETCH_RE = re.compile(r'(\bcurl\b|\bwget\b|https?://|\biwr\b|\birm\b|Invoke-WebRequest|Invoke-RestMethod|\bfetch\s*\()', re.I)
LIFECYCLE = ('preinstall', 'install', 'postinstall', 'prepare')


def lifecycle_fetch(M):
    """-> detail string or None."""
    pj = M.get('package_json') or {}
    sc = pj.get('scripts')
    if isinstance(sc, dict):
        for k in LIFECYCLE:
            v = sc.get(k)
            if isinstance(v, str) and FETCH_RE.search(v): return 'package.json scripts.%s' % k
    pp = M.get('pyproject') or {}

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                r = walk(v, path + [str(k).lower()])
                if r: return r
        elif isinstance(o, list):
            for v in o:
                r = walk(v, path)
                if r: return r
        elif isinstance(o, str):
            if any('hook' in p for p in path) and any('build' in p for p in path) and FETCH_RE.search(o):
                return '.'.join(path)
        return None
    return walk(pp.get('tool') or {}, ['tool']) or walk(pp.get('build-system') or {}, ['build-system'])


# ------------------------------------------------------------------ R6
_SH = r'(?:sudo\s+(?:-\S+\s+)*)?(?:sh|bash|zsh|python3?|node)\b'
PIPE_PATTERNS = [
    ('curl_wget_pipe_shell', re.compile(r'\b(?:curl|wget)\b[^\n|]*\|\s*' + _SH, re.I)),
    ('process_substitution', re.compile(r'(?:\b(?:sh|bash|zsh|source)\b|\.)\s+<\(\s*(?:curl|wget)\b', re.I)),
    ('iwr_irm_pipe_iex', re.compile(r'\b(?:iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^\n|]*\|\s*(?:iex|Invoke-Expression)\b', re.I)),
    ('pipe_iex', re.compile(r'\|\s*(?:iex|Invoke-Expression)\b', re.I)),
    ('iex_of_download', re.compile(r'\biex\s*\(?\s*\(?\s*(?:iwr|irm|Invoke-WebRequest|Invoke-RestMethod|New-Object\s+(?:System\.)?Net\.WebClient)', re.I)),
    ('invoke_expression', re.compile(r'\bInvoke-Expression\b', re.I)),
    ('base64_decode_pipe_shell', re.compile(r'\bbase64\s+(?:-d|-D|--decode)\b[^\n]*\|\s*' + _SH, re.I)),
    ('xxd_pipe_shell', re.compile(r'\bxxd\s+-r\b[^\n]*\|\s*' + _SH, re.I)),
    ('eval_command_substitution', re.compile(r'\beval\s+["\']?\$\(')),
    ('hex_escape_run', re.compile(r'(?:\\x[0-9a-fA-F]{2}){8,}')),
]
_B64_RUN = re.compile(r'[A-Za-z0-9+/]{40,}={0,2}')
_B64_CUE = re.compile(r'base64|-enc\b|-EncodedCommand|\beval\b|\bexec\b|\|\s*(?:sh|bash|zsh)\b|\becho\b|python3?\s+-c|node\s+-e', re.I)
_SHELLISH = re.compile(r'curl|wget|/bin/|\bbash\b|\bsh\b|powershell|\bexec\b|\beval\b|chmod|\bnc\b|rm -rf|Invoke-', re.I)


def _decodes_to_shell(tok):
    pad = tok + '=' * (-len(tok) % 4)
    try:
        raw = base64.b64decode(pad, validate=False)
    except Exception:
        return False
    for enc in ('utf-8', 'utf-16-le'):
        try:
            s = raw.decode(enc)
        except Exception:
            continue
        if s and sum(32 <= ord(c) < 127 or c in '\n\t' for c in s) / len(s) >= 0.9 and _SHELLISH.search(s):
            return True
    return False


def find_pipe_to_shell(text):
    """-> pattern name or None. text may contain several commands."""
    if not text: return None
    t = re.sub(r'\\\r?\n\s*', ' ', text)               # line continuations
    t = re.sub(r'\|\s*\r?\n\s*', '| ', t)                # pipe at end of line
    t = re.sub(r'\r?\n\s*\|\s*', ' | ', t)               # pipe at start of next line
    for name, rx in PIPE_PATTERNS:
        if rx.search(t): return name
    for ln in t.split('\n'):
        if _B64_CUE.search(ln):
            for m in _B64_RUN.finditer(ln):
                if _decodes_to_shell(m.group(0)): return 'base64_obfuscated_command'
    return None


_FENCE = re.compile(r'(?:```|~~~)[^\n]*\n(.*?)(?:```|~~~)', re.S)
_INLINE = re.compile(r'`([^`\n]{3,})`')


def code_blocks(md):
    md = (md or '')[:README_MAX]
    out = [m.group(1) for m in _FENCE.finditer(md)]
    rest = _FENCE.sub('', md)
    out += [m.group(1) for m in _INLINE.finditer(rest)]
    return out


def _strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        if isinstance(o.get('command'), str) and isinstance(o.get('args'), list):
            yield o['command'] + ' ' + ' '.join(str(a) for a in o['args'])
        for v in o.values(): yield from _strings(v)
    elif isinstance(o, list):
        for v in o: yield from _strings(v)


def pipe_to_shell(M, readme):
    """-> (pattern, where) or None."""
    for b in code_blocks(readme):
        p = find_pipe_to_shell(b)
        if p: return p, 'README'
    pj = M.get('package_json') or {}
    for k, v in (pj.get('scripts') or {}).items() if isinstance(pj.get('scripts'), dict) else []:
        if isinstance(v, str):
            p = find_pipe_to_shell(v)
            if p: return p, 'package.json scripts.' + k
    for grp in ('plugins', 'marketplaces'):
        for path, j in M.get(grp, {}).items():
            for s in _strings(j):
                p = find_pipe_to_shell(s)
                if p: return p, path
    for key in ('server_json', 'registry_server'):
        j = M.get(key)
        if j:
            for s in _strings(j):
                p = find_pipe_to_shell(s)
                if p: return p, key
    return None


# ------------------------------------------------------------------ R7
def _norm_py(n): return re.sub(r'[-_.]+', '-', str(n or '')).lower()


def _server_dicts(M):
    return [d for d in (M.get('registry_server'), M.get('server_json')) if d]


def _root_pkg_checkable(M):
    pj = M.get('package_json')
    if not pj or pj.get('private') or pj.get('workspaces'): return None
    n = pj.get('name')
    return n.lower() if isinstance(n, str) and n else None


_ARGS_JSON = re.compile(r'"args"\s*:\s*\[\s*"(?:-y|--yes)"\s*,\s*"([^"]+)"')


def _strip_ver(p):
    return re.sub(r'(?<=.)@[^@/]+$', '', p).lower()


def check_disguised(M, readme, repo_name=''):
    """-> detail or None. Manifest-vs-manifest only."""
    n_npm = _root_pkg_checkable(M)
    pp = (M.get('pyproject') or {}).get('project') or {}
    n_py = _norm_py(pp.get('name')) if pp.get('name') else None
    for sd in _server_dicts(M):
        if ((sd.get('repository') or {}).get('subfolder')): continue
        for p in sd.get('packages') or []:
            if not isinstance(p, dict): continue
            rt, ident = str(p.get('registryType', '')).lower(), p.get('identifier')
            if not isinstance(ident, str): continue
            if rt == 'npm' and n_npm and ident.lower() != n_npm:
                return 'server.json npm identifier %s != package.json name %s' % (ident, n_npm)
            if rt == 'pypi' and n_py and _norm_py(ident) != n_py:
                return 'server.json pypi identifier %s != pyproject name %s' % (ident, n_py)
    if n_npm and not any((sd.get('repository') or {}).get('subfolder') for sd in _server_dicts(M)):
        base = n_npm.split('/')[-1]
        pk = {_strip_ver(x) for x in _ARGS_JSON.findall((readme or '')[:README_MAX])}
        if pk and n_npm not in pk and base not in {x.split('/')[-1] for x in pk}:
            near = [x for x in pk if base and base in x]
            if near: return 'README config runs %s but package.json name is %s' % (near[0], n_npm)
    return None


# ------------------------------------------------------------------ top level
def curate(node, M, readme, now, from_registry=False):
    """node: GraphQL repo dict. M: parse_manifests() result. -> (ok, code|None, detail, types)."""
    owner = (node or {}).get('owner') or {}
    created = parse_ts(owner.get('createdAt'))
    if not node or not owner.get('login'):
        return False, 'owner_unclear', 'owner not resolvable', []
    if node.get('isFork'):
        return False, 'owner_unclear', 'fork', []
    if not created or (now - created).days < OWNER_MIN_DAYS:
        return False, 'owner_unclear', 'owner account younger than %d days or age unknown' % OWNER_MIN_DAYS, []
    pushed = parse_ts(node.get('pushedAt'))
    rel = parse_ts(((node.get('latestRelease') or {}).get('publishedAt')))
    newest = max([d for d in (pushed, rel) if d], default=None)
    if not newest or (now - newest).days > ACTIVE_DAYS:
        return False, 'inactive', 'no push/release in %d days' % ACTIVE_DAYS, []
    if node.get('isArchived') or node.get('isDisabled'):
        return False, 'archived_or_disabled', '', []
    if not M.get('found'):
        return False, 'no_manifest', '', []
    d = lifecycle_fetch(M)
    if d: return False, 'lifecycle_fetch', d, []
    r = pipe_to_shell(M, readme)
    if r: return False, 'pipe_to_shell', '%s in %s' % r, []
    d = check_disguised(M, readme, (node.get('nameWithOwner') or '').split('/')[-1])
    if d: return False, 'disguised_install', d, []
    types = detect_types(M, from_registry)
    if not types: return False, 'not_ai_tool', '', []
    return True, None, '', types
