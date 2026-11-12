"""Reference labels + classifier evaluation (procedure fixed by the user).
Reference per column:
  OS, arch : file content if readable; else label agreed by labeler-a and labeler-b (not both 'ragu'); else 'tidak terselesaikan'
  type     : agreed by both labelers (not both 'ragu'); else 'tidak terselesaikan'   (no file-content basis for type)
Validity rule (fixed BEFORE any metric was computed, from evidence only): a 32-bit PE header (machine 0x14c) does NOT identify the
target arch of an installer (NSIS/WiX/Inno stubs are 32-bit and install any arch; 9 of the 11 PE rows carry such markers and all 11
are 0x14c; marker detection is incomplete because 2 rows have the same machine and no marker). So for PE: OS=windows stays valid,
arch counts as file-content evidence only when machine is 64-bit (x64/arm64); otherwise arch falls back to labeler agreement.
.deb control, RPM ARCH and ELF (AppImage) reflect the target arch and stay as content evidence. Raw evidence files are unchanged.
Metrics: unresolved rows counted WRONG for the classifier (strict) and also reported with those rows excluded (range).
GATE "OS >= 95%" strictest number = min of: strict accuracy (unresolved wrong, n=100); accuracy excluding unresolved;
accuracy on file-content rows only; per-class precision(strict)/recall for windows, macos, linux. n is printed with each.
Classes the classifier can never output (e.g. arch 'any', 'other(...)') are flagged 'unproducible' in the wrong-cases list.
Usage: python scripts/14_eval_reference.py     (needs data/labeler_a.csv, data/labeler_b.csv, data/evidence_summary.json)"""
import csv, json, sys, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from classifier import classify   # read-only use; classifier.py is not modified

import os
D = pathlib.Path(os.environ['EVAL_DIR']) if os.environ.get('EVAL_DIR') else pathlib.Path(__file__).resolve().parent.parent / 'data'  # EVAL_DIR=data/clean for the clean sample
UNR, UNRES = 'tidak terbaca', 'tidak terselesaikan'
ev = json.load(open(D / 'evidence_summary.json', encoding='utf-8'))
todo = list(csv.DictReader(open(D / 'labels_todo.csv', encoding='utf-8-sig')))


def load(p):
    return {int(r['id']): {k.strip().lower(): (v or '').strip().lower() for k, v in r.items()} for r in csv.DictReader(open(D / p, encoding='utf-8-sig'))}


A, B = load('labeler_a.csv'), load('labeler_b.csv')
NROWS = len(todo)
assert len(A) == len(B) == len(todo) == len(ev) == NROWS, (len(A), len(B), len(todo), len(ev))
for _i, _r in enumerate(todo):
    assert ev[_i]['asset_name'] == _r['asset_name'] and ev[_i]['idx'] == _i, 'evidence/todo misaligned at %d' % _i
    for _L in (A, B):
        assert _i in _L and _L[_i]['os'] and _L[_i]['arch'] and _L[_i]['type'] and _L[_i]['confidence'] in ('yakin', 'ragu'), 'bad labeler row %d' % _i
COLS = [('OS', 'os', 0), ('arch', 'arch', 1), ('type', 'type', 2)]
rows, basis = [], {c: collections.Counter() for c, _, _ in COLS}
for i, r in enumerate(todo):
    pred = classify(r['asset_name'])
    row = {'id': i, 'repo': r['repo'], 'asset': r['asset_name'], 'pred': pred, 'gold': {}, 'basis': {}, 'a': A[i], 'b': B[i], 'content': (ev[i]['content_os'], ev[i]['content_arch']), 'fmt': ev[i]['evidence'].get('format')}
    for cname, key, idx in COLS:
        a, b = A[i][key if key != 'os' else 'os'], B[i][key if key != 'os' else 'os']
        both_doubt = A[i]['confidence'] == 'ragu' and B[i]['confidence'] == 'ragu'
        content = ev[i]['content_os'] if cname == 'OS' else ev[i]['content_arch'] if cname == 'arch' else UNR
        if cname == 'arch' and ev[i]['evidence'].get('format') == 'PE' and content not in ('x64', 'arm64'):
            content = UNR   # 32-bit PE: possible installer stub, arch not identified by the header
        if content != UNR:
            g, bs = content.lower(), 'isi file'
        elif a == b and not both_doubt:
            g, bs = a, 'kesepakatan dua pelabel'
        else:
            g, bs = UNRES, 'tidak terselesaikan'
        row['gold'][cname], row['basis'][cname] = g, bs
        basis[cname][bs] += 1
    rows.append(row)

out = {'basis': {c: dict(v) for c, v in basis.items()}, 'columns': {}}
for cname, key, idx in COLS:
    gold = [r['gold'][cname] for r in rows]; pred = [r['pred'][idx] for r in rows]
    res = [g != UNRES for g in gold]
    acc_strict = sum(g == p for g, p in zip(gold, pred)) / len(rows)
    n_res = sum(res); acc_excl = sum(g == p for g, p, k in zip(gold, pred, res) if k) / n_res if n_res else float('nan')
    # accuracy restricted to file-content rows (strongest evidence)
    cont = [r for r in rows if r['basis'][cname] == 'isi file']
    acc_content = sum(r['gold'][cname] == r['pred'][idx] for r in cont) / len(cont) if cont else None
    classes = {}
    for c in sorted({g for g in gold if g != UNRES} | set(pred)):
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp_strict = sum(g != c and p == c for g, p in zip(gold, pred))            # unresolved gold counts as wrong
        fp_excl = sum(g != c and p == c and k for g, p, k in zip(gold, pred, res))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        classes[c] = {'tp': tp, 'fp_strict': fp_strict, 'fp_excl': fp_excl, 'fn': fn,
                      'precision_strict': tp / (tp + fp_strict) if tp + fp_strict else None,
                      'precision_excl': tp / (tp + fp_excl) if tp + fp_excl else None,
                      'recall': tp / (tp + fn) if tp + fn else None}
    out['columns'][cname] = {'accuracy_strict_unresolved_wrong': acc_strict, 'accuracy_unresolved_excluded': acc_excl, 'n_resolved': n_res,
                             'accuracy_file_content_rows': acc_content, 'n_file_content_rows': len(cont), 'classes': classes}

# independent sanity check of the name-based labelers against file content
chk = {}
for cname, key in (('OS', 'os'), ('arch', 'arch')):
    c_rows = [r for r in rows if r['basis'][cname] == 'isi file']
    chk[cname] = {'n': len(c_rows), 'labeler_a_match': sum(r['a'][key] == r['gold'][cname] for r in c_rows), 'labeler_b_match': sum(r['b'][key] == r['gold'][cname] for r in c_rows)}
out['labelers_vs_content'] = chk
out['labeler_agreement'] = {c: sum(A[i][k] == B[i][k] for i in range(NROWS)) for c, k in (('OS', 'os'), ('arch', 'arch'), ('type', 'type'))}
out['confidence_counts'] = {'a': dict(collections.Counter(A[i]['confidence'] for i in A)), 'b': dict(collections.Counter(B[i]['confidence'] for i in B))}
PRODUCIBLE = {'OS': {'windows', 'macos', 'linux', 'android', 'ios', 'unknown'}, 'arch': {'x64', 'arm64', 'arm32', 'x86', 'universal', 'unknown'}, 'type': {'installer', 'portable', 'ambiguous', 'not_installer'}}
# gate: strictest OS number
osd = out['columns']['OS']
gate = {'strict_unresolved_wrong_n%d' % NROWS: osd['accuracy_strict_unresolved_wrong'], 'excluding_unresolved_n%d' % osd['n_resolved']: osd['accuracy_unresolved_excluded'],
        'file_content_rows_n%d' % osd['n_file_content_rows']: osd['accuracy_file_content_rows']}
for cls in ('windows', 'macos', 'linux'):
    k = osd['classes'].get(cls)
    if k:
        gate['precision_strict_' + cls] = k['precision_strict']; gate['recall_' + cls] = k['recall']
vals = {k: v for k, v in gate.items() if v is not None}
out['gate_OS'] = {'numbers': gate, 'strictest': min(vals.items(), key=lambda kv: kv[1]), 'passes_95': min(vals.values()) >= 0.95}
out['wrong'] = [{'col': c, 'id': r['id'], 'repo': r['repo'], 'asset': r['asset'], 'gold': r['gold'][c], 'basis': r['basis'][c], 'pred': r['pred'][i2], 'unproducible': r['gold'][c] not in PRODUCIBLE[c]} for r in rows for c, _, i2 in COLS if r['gold'][c] != UNRES and r['gold'][c] != r['pred'][i2]]
out['unresolved'] = [{'col': c, 'id': r['id'], 'repo': r['repo'], 'asset': r['asset'], 'a': (r['a'][k], r['a']['confidence']), 'b': (r['b'][k], r['b']['confidence']), 'pred': r['pred'][i2]} for r in rows for c, k, i2 in COLS if r['gold'][c] == UNRES]
json.dump(out, open(D / 'eval_result.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
json.dump([{k: v for k, v in r.items()} for r in rows], open(D / 'reference_labels.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(json.dumps({k: out[k] for k in ('basis', 'labelers_vs_content', 'labeler_agreement', 'confidence_counts')}, indent=1))
for c in ('OS', 'arch', 'type'):
    d = out['columns'][c]; f = lambda x: 'n/a' if x is None else '%.3f' % x
    print(c, 'acc strict', f(d['accuracy_strict_unresolved_wrong']), '| excl-unresolved', f(d['accuracy_unresolved_excluded']), 'n=%d' % d['n_resolved'], '| file-content rows', f(d['accuracy_file_content_rows']), 'n=%d' % d['n_file_content_rows'])
print('wrong', len(out['wrong']), 'unresolved cells', len(out['unresolved']))
print('GATE OS', json.dumps(out['gate_OS'], indent=1))
