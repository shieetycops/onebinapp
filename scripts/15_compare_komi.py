"""Compare four classifiers on rows with reference labels (default: the 100 DEV rows in data/reference_labels.json).
  v1 = classifier.py (frozen), komi_port = komi as ported, komi_pipe = komi pipeline-equivalent, v2 = classifier_v2.py
Usage: python scripts/15_compare_komi.py [reference_labels.json] [out.json]
Per column: accuracy (unresolved wrong / excluded), per-class precision + recall, and per-row differences with the basis of the gold label."""
import json, sys, pathlib, collections, hashlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classifier, komi_classifier, classifier_v2
D = HERE.parent / 'data'
src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else D / 'reference_labels.json'
dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else D / 'compare_four.json'
rows = json.load(open(src, encoding='utf-8'))
UNRES = 'tidak terselesaikan'
CLF = {'v1': classifier.classify, 'komi_port': komi_classifier.classify, 'komi_pipe': komi_classifier.classify_pipeline, 'v2': classifier_v2.classify}
COLS = [('OS', 0), ('arch', 1), ('type', 2)]
n = len(rows)
out = {'n_rows': n, 'source': str(src.name), 'sha256': {f: hashlib.sha256((HERE / f).read_bytes()).hexdigest() for f in ('classifier.py', 'classifier_v2.py', 'komi_classifier.py')}, 'columns': {}, 'diffs': []}
preds = {k: [f(r['asset']) for r in rows] for k, f in CLF.items()}
for c, i in COLS:
    gold = [r['gold'][c] for r in rows]; ok = [g != UNRES for g in gold]; nr = sum(ok)
    col = {}
    for k in CLF:
        p = [x[i] for x in preds[k]]
        classes = {}
        for cl in sorted({g for g in gold if g != UNRES} | set(p)):
            tp = sum(g == cl and q == cl for g, q in zip(gold, p)); fp = sum(g != cl and q == cl for g, q in zip(gold, p)); fn = sum(g == cl and q != cl for g, q in zip(gold, p))
            classes[cl] = {'tp': tp, 'fp': fp, 'fn': fn, 'P': tp / (tp + fp) if tp + fp else None, 'R': tp / (tp + fn) if tp + fn else None}
        col[k] = {'acc_strict': sum(g == q for g, q in zip(gold, p)) / n, 'acc_excl': sum(g == q for g, q, o in zip(gold, p, ok) if o) / nr, 'n_resolved': nr, 'classes': classes}
    out['columns'][c] = col
    for j, r in enumerate(rows):
        g = r['gold'][c]
        if g == UNRES: continue
        pr = {k: preds[k][j][i] for k in CLF}
        if len({pr[k] == g for k in CLF}) > 1:
            out['diffs'].append({'col': c, 'id': r['id'], 'asset': r['asset'], 'gold': g, 'basis': r['basis'][c], **{k: pr[k] for k in CLF}, 'right': [k for k in CLF if pr[k] == g]})
json.dump(out, open(dst, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
f = lambda x: 'n/a' if x is None else '%.2f' % x
for c, _ in COLS:
    print('==', c, '(n resolved %d)' % out['columns'][c]['v1']['n_resolved'])
    for k in CLF:
        d = out['columns'][c][k]; print('  %-9s strict %.3f  excl %.3f' % (k, d['acc_strict'], d['acc_excl']))
        print('      ', ' '.join('%s P%s/R%s' % (cl, f(v['P']), f(v['R'])) for cl, v in d['classes'].items()))
print(len(out['diffs']), 'differing cells (written to', dst.name + ')')
