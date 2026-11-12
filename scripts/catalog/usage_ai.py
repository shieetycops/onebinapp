"""Section "Cara pakai" for AI-tool detail pages (stdlib only).  Pure functions: no network, nothing from the repo is executed.
Every README / manifest string is DATA: it is cleaned to plain text (HTML tags, markdown link syntax, backticks removed) and the site
renders it as text only.  Each part is either {ok:True,...} or the single "empty" shape {ok:False, unavailable:True, readme_url}.

Parts per entry (usage.by_type[type]):  abilities ("Yang bisa dilakukan"), examples ("Contoh pakai"), settings ("Pengaturan yang perlu diisi")
Parts per tool x type (usage.by_tool[tool][type]): after ("Setelah terpasang"), uninstall ("Cara mencopot")
Official per-tool text comes only from usage_methods.json (every cell has a source_url, written from site/research/usage_methods.md)."""
import re, json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
FORBIDDEN = re.compile(r'\b(' + 'am' + 'an' + r'|safe)\b', re.I)
METHODS = json.loads((HERE / 'usage_methods.json').read_text(encoding='utf-8')) if (HERE / 'usage_methods.json').exists() else {}
TOOLS = ['claude-code', 'claude-desktop', 'cursor', 'vscode', 'codex']

_TAG = re.compile(r'<[^>]*>')
_LINK = re.compile(r'!?\[([^\]]*)\]\([^)]*\)')
_URL = re.compile(r'https?://\S+')
_CTRL = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')


def clean(s, n=220, keep_urls=False):
    """-> plain one-line text, or '' when nothing is left."""
    if not isinstance(s, str): return ''
    s = _CTRL.sub(' ', s)
    s = _LINK.sub(r'\1', s)
    s = _TAG.sub(' ', s)
    s = s.replace('`', '').replace('\\', '')
    if not keep_urls: s = _URL.sub('', s)
    s = s.replace('*', '')
    s = re.sub(r'^#+\s*', '', s)
    s = re.sub(r'\s+', ' ', s).strip(' -:–—')
    if len(s) > n: s = s[:n - 1].rstrip() + '…'
    return s


def ok_text(s):
    return bool(s) and not FORBIDDEN.search(s)


def unavailable(repo):
    return {'ok': False, 'unavailable': True, 'readme_url': 'https://github.com/%s#readme' % repo}


# ------------------------------------------------------------------ abilities
def _first_sentence(s, n=160):
    s = clean(s, 400)
    m = re.match(r'(.{8,}?[.!?])(\s|$)', s)
    out = m.group(1) if m else s
    return out if len(out) <= n else out[:n - 1].rstrip() + '…'


def registry_tools(server):
    """Tool list published by the registry entry itself (_meta publisher-provided 'tools').  Free-form: only list-of-strings or
    list-of-{name,description} are used.  Returns [{name, desc|None}]."""
    meta = ((server or {}).get('_meta') or {}).get('io.modelcontextprotocol.registry/publisher-provided') or {}
    t = meta.get('tools') if isinstance(meta, dict) else None
    out = []
    if isinstance(t, list):
        for x in t:
            if isinstance(x, str): nm, ds = x, None
            elif isinstance(x, dict) and isinstance(x.get('name'), str): nm, ds = x['name'], x.get('description')
            else: continue
            nm = clean(nm, 80)
            ds = _first_sentence(ds) if ds else None
            if nm and ok_text(nm) and (ds is None or ok_text(ds)): out.append({'name': nm, 'desc': ds})
    return out[:40]


def plugin_components(M, ufile):
    """Commands, agents, hooks of the plugin the install command installs.  ufile = cached usage_fetch record or None."""
    if not ufile or ufile.get('base') is None: return None
    comp = {'commands': [], 'agents': [], 'hooks': []}
    base = ufile['base']
    pj = None
    if ufile.get('plugin_json'):
        try: pj = json.loads(ufile['plugin_json'])
        except Exception: pj = None
    if pj is None and not base:
        pj = (M.get('plugins') or {}).get('.claude-plugin/plugin.json') or (M.get('plugins') or {}).get('plugin.json')
    fm = ufile.get('fm') or {}

    def fm_desc(prefix, fname):
        t = fm.get((base + '/' if base else '') + prefix + '/' + fname) or ''
        m = re.search(r'^---\s*\n(.*?)\n---', t, re.S)
        if m:
            d = re.search(r'^description:\s*(.+)$', m.group(1), re.M)
            if d: return _first_sentence(d.group(1).strip('"\' '))
        return None
    for key, folder in (('commands', 'commands'), ('agents', 'agents')):
        for f in ufile.get(key) or []:
            if not f.endswith('.md'): continue      # slash commands / agents are markdown files; .toml etc. belong to other tools
            nm = re.sub(r'\.md$', '', f)
            if not re.match(r'^[A-Za-z0-9._-]{1,60}$', nm): continue
            desc = fm_desc(folder, f) if f.endswith('.md') else None
            if desc and not ok_text(desc): desc = None
            if not ok_text(nm): continue
            comp[key].append({'name': nm, 'desc': desc})
    hooks = None
    if ufile.get('hooks_json'):
        try: hooks = json.loads(ufile['hooks_json'])
        except Exception: hooks = None
    if hooks is None and isinstance(pj, dict) and isinstance(pj.get('hooks'), dict): hooks = pj
    if isinstance(hooks, dict):
        hk = hooks.get('hooks') if isinstance(hooks.get('hooks'), dict) else None
        for ev, lst in (hk or {}).items():
            if not isinstance(lst, list) or not re.match(r'^[A-Za-z]{3,40}$', str(ev)): continue
            for g in lst[:6]:
                if not isinstance(g, dict): continue
                matcher = clean(g.get('matcher') or '', 60)
                for h in (g.get('hooks') or [])[:3]:
                    if isinstance(h, dict) and h.get('type') == 'command' and isinstance(h.get('command'), str):
                        c = clean(h['command'], 110, keep_urls=True)
                        if ok_text(c): comp['hooks'].append({'event': str(ev), 'matcher': matcher or None, 'command': c})
    return comp


def abilities(types_for, M, repo, server, ufile):
    """-> {type: part}"""
    out = {}
    if 'mcp' in types_for:
        tl = registry_tools(server)
        out['mcp'] = ({'ok': True, 'kind': 'tools', 'items': tl, 'source': 'registry'} if tl else unavailable(repo))
    if 'skill' in types_for:
        items = []
        for s in M.get('skills') or []:
            nm, ds = clean(s.get('name'), 80), _first_sentence(s.get('description'), 300)
            if nm and ds and ok_text(nm) and ok_text(ds): items.append({'name': nm, 'desc': ds})
        out['skill'] = ({'ok': True, 'kind': 'skills', 'items': items[:5], 'source': 'SKILL.md frontmatter'} if items else unavailable(repo))
    if 'plugin' in types_for:
        comp = plugin_components(M, ufile)
        if comp and (comp['commands'] or comp['agents'] or comp['hooks']):
            out['plugin'] = {'ok': True, 'kind': 'plugin', 'source': 'plugin.json / folder commands, agents, hooks', **comp}
        else:
            out['plugin'] = unavailable(repo)
    return out


# ------------------------------------------------------------------ examples
_HEAD = re.compile(r'^\s{0,3}#{1,4}\s*(.+?)\s*#*\s*$')
_WANT = re.compile(r'example|usage|prompt|try (it|asking)|how to use|what you can (ask|do)|ask (claude|your)|sample', re.I)
_QUOTED = re.compile(r'^\s*(?:[-*+]\s+|>\s*|\d+[.)]\s+)\s*["“]([^"”]{12,200})["”]\s*[.!?]?\s*$')
_BAD = re.compile(r'[<>{}|$\\]|https?://|\bnpx\b|\bcurl\b|\bsudo\b|\bpip\b|\brm -')




_PLAIN = re.compile(r"^[A-Z][A-Za-z0-9 ,'\u2019\"\u201c\u201d.?!/-]{14,180}$")
_FENCE_LANG_OK = {'', 'text', 'txt', 'prompt', 'plaintext', 'plain'}
_SHELLY = re.compile(r'^(?:[A-Z][A-Za-z]*=|Usage:|Options:|Example:|Note:|Warning:|Returns?:|Output:|Input:)')


def readme_examples(readme, limit=3):
    """Prompts that the README itself shows, by two narrow rules, only under an Example/Usage/Prompts heading:
    (1) quoted bullet or blockquote lines; (2) plain-sentence lines (capital first letter, 4+ words, no shell/JSON/URL characters)
    inside a fenced block with no language or text/prompt.  Max 3."""
    out, active, fence, lang_ok = [], False, False, False
    for line in (readme or '').splitlines():
        st = line.strip()
        if st.startswith('```'):
            if not fence: fence, lang_ok = True, st[3:].strip().lower() in _FENCE_LANG_OK
            else: fence, lang_ok = False, False
            continue
        if fence:
            if active and lang_ok and _PLAIN.match(st) and len(st.split()) >= 4 and not _BAD.search(st) and not _SHELLY.match(st) and not st.endswith((',', ':')):
                t = clean(st, 200)
                if len(t) >= 12 and ok_text(t) and t not in out: out.append(t)
                if len(out) >= limit: break
            continue
        m = _HEAD.match(line)
        if m: active = bool(_WANT.search(m.group(1))); continue
        if not active: continue
        q = _QUOTED.match(line)
        if q:
            t = clean(q.group(1), 200)
            if len(t) >= 12 and not _BAD.search(q.group(1)) and ok_text(t) and t not in out: out.append(t)
            if len(out) >= limit: break
    return out


def auto_examples(types_for, name, desc, skills, comp):
    nm = clean(name, 60) or 'ini'
    ds = clean(desc, 140)
    ex = []
    if 'mcp' in types_for:
        ex += ['Tampilkan daftar tool yang disediakan server %s.' % nm, 'Apa saja yang bisa saya lakukan dengan server %s?' % nm]
    if 'skill' in types_for and skills:
        s = skills[0]
        ex += ['Gunakan skill %s untuk pekerjaan ini: %s' % (s['name'], clean(s['desc'], 120))]
    if 'plugin' in types_for:
        c = (comp or {}).get('commands') or []
        if c: ex += ['/%s' % c[0]['name']]
        ex += ['Jelaskan apa yang bisa saya lakukan dengan plugin %s.' % nm]
    out = []
    for e in ex:
        e = clean(e, 200)
        if ok_text(e) and e not in out: out.append(e)
    return out[:3]


def examples(types_for, name, desc, readme, M, comp, repo):
    real = readme_examples(readme)
    if real: return {'ok': True, 'source': 'readme', 'auto': False, 'items': real, 'readme_url': 'https://github.com/%s#readme' % repo}
    auto = auto_examples(types_for, name, desc, [s for s in abilities_skills(M)], comp)
    if auto: return {'ok': True, 'source': 'auto', 'auto': True, 'items': auto}
    return unavailable(repo)


def abilities_skills(M):
    out = []
    for s in M.get('skills') or []:
        nm, ds = clean(s.get('name'), 80), _first_sentence(s.get('description'), 300)
        if nm and ds: out.append({'name': nm, 'desc': ds})
    return out


# ------------------------------------------------------------------ settings
def settings(M, server_dict_fn, repo):
    """Env vars / headers the server.json asks for.  Description is used as 'where to get it' only when the manifest provides one."""
    sd = server_dict_fn(M) or {}
    items = []
    for p in sd.get('packages') or []:
        if not isinstance(p, dict): continue
        for e in p.get('environmentVariables') or []:
            if isinstance(e, dict) and re.match(r'^[A-Za-z_][A-Za-z0-9_]{0,63}$', str(e.get('name', ''))):
                d = clean(e.get('description') or '', 200)
                items.append({'name': e['name'], 'required': bool(e.get('isRequired')), 'secret': bool(e.get('isSecret')),
                              'where': d if ok_text(d) else None})
    for r in sd.get('remotes') or []:
        if isinstance(r, dict):
            for h in r.get('headers') or []:
                if isinstance(h, dict) and re.match(r'^[A-Za-z0-9-]{1,60}$', str(h.get('name', ''))):
                    d = clean(h.get('description') or '', 200)
                    items.append({'name': h['name'], 'required': bool(h.get('isRequired')), 'secret': bool(h.get('isSecret')),
                                  'where': d if ok_text(d) else None, 'header': True})
    seen, uniq = set(), []
    for i in items:
        if i['name'] not in seen: seen.add(i['name']); uniq.append(i)
    if uniq: return {'ok': True, 'items': uniq[:12], 'source': 'server.json'}
    return {'ok': True, 'items': [], 'none_listed': True, 'source': 'server.json'} if sd else None


# ------------------------------------------------------------------ per tool
def _fill(t, ctx):
    """Replace only the known {placeholders}; other braces (JSON examples) stay as written."""
    if not isinstance(t, str): return t
    return re.sub(r'\{(name|cc_plugin|cc_marketplace|cx_plugin|cx_marketplace|skill_name)\}', lambda m: ctx.get(m.group(1), m.group(0)), t)


def per_tool(tool, type_key, method, ctx, want_settings=False):
    """-> {after, uninstall[, settings]} for a tool x type whose install method exists (kind != none); else None."""
    if not method or method.get('kind') == 'none': return None
    cell = (METHODS.get(tool) or {}).get(type_key) or {}
    out = {}
    for part in ('after', 'uninstall') + (('settings',) if want_settings else ()):
        c = cell.get(part)
        if c and c.get('steps') and c.get('source_url'):
            if c.get('needs') and not all(ctx.get(k) for k in c['needs']):
                out[part] = {'ok': False, 'unavailable': True}
                continue
            out[part] = {'ok': True, 'steps': [_fill(x, ctx) for x in c['steps']], 'source_url': c['source_url'],
                         'config_file': c.get('config_file'), 'note': c.get('note'), 'inferred': bool(c.get('inferred'))}
        else:
            out[part] = {'ok': False, 'unavailable': True, 'doc_gap': True}
    return out


def _mk_ctx(M, repo, IA):
    ctx = {'name': IA.install_name(M, repo)}
    mks = M.get('marketplaces') or {}
    cc = mks.get('.claude-plugin/marketplace.json')
    if cc and isinstance(cc.get('name'), str):
        nm = IA._plugin_names(cc)
        if nm: ctx['cc_plugin'], ctx['cc_marketplace'] = nm[0], cc['name']
    cx = mks.get('.agents/plugins/marketplace.json')
    if cx and isinstance(cx.get('name'), str):
        nm = IA._plugin_names(cx)
        if nm: ctx['cx_plugin'], ctx['cx_marketplace'] = nm[0], cx['name']
    sk = M.get('skills') or []
    if sk: ctx['skill_name'] = sk[0]['name']
    return {k: v for k, v in ctx.items() if re.match(r'^[A-Za-z0-9._ -]{1,80}$', str(v))}


def build(M, repo, types, inst, server, name, desc, readme, ufile, IA, server_dict_fn):
    """-> usage dict stored in ai/<slug>.json"""
    ab = abilities(types, M, repo, server, ufile)
    comp = plugin_components(M, ufile) if 'plugin' in types else None
    st = settings(M, server_dict_fn, repo) if 'mcp' in types else None
    ctx = _mk_ctx(M, repo, IA)
    by_tool = {}
    for tool in TOOLS:
        cell = {}
        for t in types:
            pt = per_tool(tool, t, (inst.get(tool) or {}).get(t), ctx, want_settings=(t == 'mcp' and bool(st and st.get('items'))))
            if pt: cell[t] = pt
        if cell: by_tool[tool] = cell
    return {'readme_url': 'https://github.com/%s#readme' % repo, 'abilities': ab,
            'examples': examples(types, name, desc, readme, M, comp, repo),
            'settings': (st if st else unavailable(repo)) if 'mcp' in types else {'ok': False, 'na': True}, 'by_tool': by_tool}
