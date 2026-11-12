"""Curation rules C1-C4b, copied verbatim from scripts/18_draw_round3.py (curate(), TOK, BAD, GUI).
Do not edit the rules: tests/test_catalog.py asserts they reproduce data/round3/curation_decisions.json.
Plus adapters (GraphQL node -> REST-like metadata) and the manual deny lists."""
import json, re, pathlib

TOK = re.compile(r'[a-z0-9]+')
BAD = set('library lib framework sdk boilerplate template starter plugin extension theme icons dotfiles awesome tutorial example demo driver firmware kernel compiler linter backend'.split())
GUI = {'desktop-app', 'electron', 'tauri', 'gui', 'qt', 'gtk', 'desktop', 'flutter-desktop'}


def curate(m):
    why = []
    if m.get('fork') or m.get('archived') or m.get('disabled'): why.append('C1')
    if (m.get('stargazers_count') or 0) < 100: why.append('C2')
    if not (m.get('description') or '').strip(): why.append('C3')
    topics = [t.lower() for t in m.get('topics') or []]
    toks = set(TOK.findall((m.get('name') or '').lower())) | set(TOK.findall((m.get('description') or '').lower())) | {x for t in topics for x in TOK.findall(t)}
    hit = sorted(toks & BAD)
    if hit: why.append('C4a:' + ','.join(hit))
    if ('cli' in topics or 'command-line' in topics) and not (set(topics) & GUI): why.append('C4b')
    return why


def meta_from_graphql(node):
    """Map a GraphQL repository node to the REST meta keys used by curate()."""
    nwo = node.get('nameWithOwner') or ''
    topics = [((n or {}).get('topic') or {}).get('name') for n in ((node.get('repositoryTopics') or {}).get('nodes') or [])]
    return {'name': nwo.split('/', 1)[-1], 'description': node.get('description'),
            'fork': bool(node.get('isFork')), 'archived': bool(node.get('isArchived')), 'disabled': bool(node.get('isDisabled')),
            'stargazers_count': node.get('stargazerCount') or 0, 'topics': [t for t in topics if t]}


def curate_rest_file(path):
    """Round-3 gate helper: curation flag and reasons from a cached REST *.meta.json (error bodies -> not curated)."""
    try:
        m = json.loads(pathlib.Path(path).read_bytes())
    except Exception:
        return False, ['meta_unreadable']
    if not isinstance(m, dict) or 'full_name' not in m:
        return False, ['meta_http_error']
    why = curate(m)
    return (not why), why


def load_denied(data_dir):
    """Manual deny lists (case-insensitive set of owner/repo)."""
    d = pathlib.Path(data_dir)
    out = {}
    for fn, key in (('curation.json', 'denied'), ('curation_extra_deny.json', None)):
        p = d / fn
        if not p.exists(): continue
        j = json.loads(p.read_text(encoding='utf-8'))
        if key: j = j.get(key, {})
        for k, v in j.items(): out[k.lower()] = v
    return out
