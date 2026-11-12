"""Round 3 gate, as data/round3/LOCK.md sections 0a, 5, 6, 7. Run: python -I scripts/19_gate_round3.py
Reads data/round3/{all_assets,id_map,curation_decisions,evidence_summary}.json, data/labeler3/out_{a,b}/labels_NN.csv.
Writes data/round3/gate_round3.json and data/round3/dmg_pkg_sample.json (seed 20261120, sorted 'repo|asset' list, 30)."""
import csv, json, math, pathlib, random, sys, collections
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import picker_v3 as P, classifier_v3 as C
D = HERE.parent / 'data'; R3 = D / 'round3'; L3 = D / 'labeler3'
UNRES = 'tidak terselesaikan'
assets = json.load(open(R3 / 'all_assets.json', encoding='utf-8'))
idmap = json.load(open(R3 / 'id_map.json'))
dec = json.load(open(R3 / 'curation_decisions.json'))
ev = json.load(open(R3 / 'evidence_summary.json', encoding='utf-8'))
assert len(assets) == len(idmap) == len(ev)


def load(side):
    out = {}
    for c in (1, 2):
        for r in csv.DictReader(open(L3 / f'out_{side}' / f'labels_{c:02d}.csv', encoding='utf-8-sig')):
            out[int(r['id'])] = {k.strip().lower(): (v or '').strip().lower() for k, v in r.items()}
    return out


A, B = load('a'), load('b')
assert set(A) == set(B) == set(range(len(assets))), 'labeler rows incomplete'


def agree(i, col, conf):
    a, b = A[i], B[i]
    if a[col] == b[col] and a[conf] != 'ragu' and b[conf] != 'ragu': return a[col]
    return UNRES


gold = []
for i, a in enumerate(assets):
    assert idmap[i]['asset_name'] == a['asset_name'] and ev[i]['asset_name'] == a['asset_name']
    e = ev[i]; fmt = e['evidence'].get('format')
    g = {'id': i, 'repo': a['repo'], 'name': a['asset_name'], 'ext': a['ext'], 'source': a['source']}
    cos = e['content_os']; g['OS'] = cos if cos != 'tidak terbaca' else agree(i, 'os', 'conf_os')
    car = e['content_arch']
    if fmt == 'PE' and car not in ('x64', 'arm64'): car = 'tidak terbaca'   # 32-bit PE rule
    if a['ext'] in ('dmg', 'msix', 'appx'): car = 'tidak terbaca'          # names only
    if car != 'tidak terbaca': g['arch'], g['arch_basis'] = car, 'isi file'
    else: g['arch'], g['arch_basis'] = agree(i, 'arch', 'conf_arch'), 'label'
    if g['arch'] == 'any': g['arch'] = 'universal'
    g['type'] = agree(i, 'type', 'conf_type'); g['role'] = agree(i, 'role', 'conf_type')
    gold.append(g)

by_repo = collections.defaultdict(list)
for g in gold: by_repo[g['repo']].append(g)
OSX = {'windows': ('exe', 'msi', 'msix', 'appx'), 'macos': ('dmg', 'pkg'), 'linux': ('appimage',)}


def status(g, cell):
    """-> ('correct'|'wrong'|'unverified', strict_correct). strict_correct: old rule (arch unknown/unresolved = not correct)."""
    os_, arch = cell
    fields = (g['OS'], g['role'], g['type'])
    if UNRES in fields: return 'unverified', False
    if g['OS'] != os_ or g['role'] != 'app' or (g['ext'] == 'exe' and g['type'] != 'installer') or g['type'] == 'not_installer':
        return 'wrong', False
    if g['arch'] in ('unknown', UNRES): return 'unverified', False
    ok = g['arch'] in P.COMPAT[cell]
    return ('correct' if ok else 'wrong'), ok


def wilson(k, n, z=1.96):
    if not n: return None
    p = k / n; d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


out = {'cells': {}, 'os': {}, 'n_repos_curated': sum(d['curated'] for d in dec.values()), 'n_assets': len(assets)}
offered_all = collections.defaultdict(list)   # for the dmg/pkg sample population
for cell in P.GATED_CELLS:
    os_, arch = cell
    qual = [r for r, gs in by_repo.items() if any(g['ext'] in OSX[os_] for g in gs)]
    stat = {'qualifying_repos': len(qual), 'offered': 0, 'verified': 0, 'correct': 0, 'wrong': 0, 'unverified': 0, 'strict_correct': 0, 'exact_arch': 0,
            'cov_num': 0, 'cov_den': 0, 'cov_den_unverified_only': 0, 'offered_any_repos': 0, 'wrong_cases': [], 'by_source': {}}
    for r in qual:
        gs = by_repo[r]
        names = [g['name'] for g in gs]
        pk = P.pick(names, os_, arch)
        sts = {g['name']: status(g, cell) for g in gs}
        any_correct = any(s[0] == 'correct' for s in sts.values())
        only_unver = (not any_correct) and all(s[0] in ('unverified', 'wrong') for s in sts.values()) and any(s[0] == 'unverified' and gs_ext in OSX[os_] for gs_ext, s in ((g['ext'], sts[g['name']]) for g in gs))
        # coverage denominator: >=1 CORRECT candidate, or candidates all unverifiable with none correct
        cand_unver = any(sts[g['name']][0] == 'unverified' and g['ext'] in OSX[os_] for g in gs)
        if any_correct: stat['cov_den'] += 1
        elif cand_unver and not any(s[0] == 'correct' for s in sts.values()): stat['cov_den'] += 1; stat['cov_den_unverified_only'] += 1
        if pk is None: continue
        g = next(x for x in gs if x['name'] == pk)
        s, strict = sts[pk]
        stat['offered'] += 1; stat['offered_any_repos'] += 1
        src = stat['by_source'].setdefault(g['source'], {'offered': 0, 'verified': 0, 'correct': 0})
        src['offered'] += 1
        stat['strict_correct'] += int(strict)
        if g['arch'] in (arch, 'universal'): stat['exact_arch'] += 1
        if s == 'unverified': stat['unverified'] += 1
        else:
            stat['verified'] += 1; src['verified'] += 1
            if s == 'correct': stat['correct'] += 1; src['correct'] += 1; stat['cov_num'] += 1
            else: stat['wrong'] += 1; stat['wrong_cases'].append({'repo': r, 'asset': pk, 'gold': {k: g[k] for k in ('OS', 'arch', 'type', 'role')}})
        if s == 'correct' and not any(x for x in []): pass
        if os_ == 'macos' and g['ext'] in ('dmg', 'pkg') and C.classify(pk)[1] == 'unknown':
            offered_all[r + '|' + pk].append(cell[1])
    v = stat['verified']
    stat['precision_verified'] = stat['correct'] / v if v else None
    stat['precision_verified_wilson_lo'] = wilson(stat['correct'], v)
    stat['precision_strict_old'] = stat['strict_correct'] / stat['offered'] if stat['offered'] else None
    stat['precision_exact_arch'] = stat['exact_arch'] / stat['offered'] if stat['offered'] else None
    stat['unverified_pct'] = stat['unverified'] / stat['offered'] if stat['offered'] else None
    stat['coverage_strict'] = stat['cov_num'] / stat['cov_den'] if stat['cov_den'] else None
    out['cells'][f'{os_}_{arch}'] = stat
for os_ in ('windows', 'macos', 'linux'):
    cs = [v for k, v in out['cells'].items() if k.startswith(os_)]
    nums = {}
    for k, v in out['cells'].items():
        if k.startswith(os_):
            if v['precision_verified'] is not None: nums['precision_' + k] = v['precision_verified']
            if v['coverage_strict'] is not None: nums['coverage_' + k] = v['coverage_strict']
    small = [k for k, v in out['cells'].items() if k.startswith(os_) and v['verified'] < 30]
    qual_n = cs[0]['qualifying_repos']
    name, val = min(nums.items(), key=lambda kv: kv[1]) if nums else (None, None)
    tgt = lambda n: 0.98 if n.startswith('precision') else 0.90
    meets = all(v >= tgt(n) for n, v in nums.items())
    out['os'][os_] = {'strictest': [name, val], 'numbers': nums, 'meets_targets': meets, 'n_kecil_cells': small, 'qualifying_repos': qual_n,
                      'passes_before_sample': bool(meets and not small and qual_n >= 60 and len(nums) == len(cs) * 2),
                      'unverified_pct_by_cell': {k: v['unverified_pct'] for k, v in out['cells'].items() if k.startswith(os_)}}
pop = sorted(offered_all)
smp = sorted(random.Random(20261120).sample(pop, 30)) if len(pop) > 30 else pop
json.dump({'population_n': len(pop), 'sample_n': len(smp), 'seed': 20261120,
           'items': [{'key': k, 'cells_offered': offered_all[k], 'url': next(a['url'] for a in assets if a['repo'] + '|' + a['asset_name'] == k)} for k in smp]},
          open(R3 / 'dmg_pkg_sample.json', 'w'), indent=1)
out['sample'] = {'population_n': len(pop), 'sample_n': len(smp)}
json.dump(out, open(R3 / 'gate_round3.json', 'w'), indent=1, ensure_ascii=False)
f = lambda x: 'n/a' if x is None else '%.3f' % x
for k, v in out['cells'].items():
    print(k, 'qual', v['qualifying_repos'], 'offered', v['offered'], 'verified', v['verified'], 'correct', v['correct'], 'wrong', v['wrong'], 'unver', v['unverified'],
          '| P_ver', f(v['precision_verified']), 'wilsonLo', f(v['precision_verified_wilson_lo']), 'P_old', f(v['precision_strict_old']), 'P_exact', f(v['precision_exact_arch']),
          'unver%', f(v['unverified_pct']), '| cov', f(v['coverage_strict']), '(%d/%d, unver-only den %d)' % (v['cov_num'], v['cov_den'], v['cov_den_unverified_only']))
for o, v in out['os'].items(): print(o, 'strictest', v['strictest'], 'meets', v['meets_targets'], 'n_kecil', v['n_kecil_cells'], 'pass_before_sample', v['passes_before_sample'])
print('dmg/pkg sample', out['sample'])
