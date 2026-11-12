"""Gate 'OS >= 95%' for every classifier on one reference set (same definition as scripts/14_eval_reference.py, rule 8 of DRAW_RULE.md).
Usage: python scripts/17_gate_all.py data/clean/reference_labels.json out.json
Numbers: strict acc (unresolved wrong), acc excluding unresolved, acc on file-content rows, and precision (strict) / recall for windows, macos, linux.
Classes with < 30 reference rows are flagged 'n kecil'. Also prints arch and type accuracy and per-class P/R for them."""
import json, sys, pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classifier, classifier_v2, komi_classifier
rows = json.load(open(sys.argv[1], encoding='utf-8'))
UNRES = 'tidak terselesaikan'
CLF = {'v1': classifier.classify, 'komi_port': komi_classifier.classify, 'komi_pipe': komi_classifier.classify_pipeline, 'v2': classifier_v2.classify}
n = len(rows)
out = {'n': n}
for col, i in (('OS', 0), ('arch', 1), ('type', 2)):
    gold = [r['gold'][col] for r in rows]; basis = [r['basis'][col] for r in rows]
    res = [g != UNRES for g in gold]
    out[col] = {'basis_counts': {b: basis.count(b) for b in set(basis)}}
    for k, f in CLF.items():
        p = [f(r['asset'])[i] for r in rows]
        strict = sum(g == q for g, q in zip(gold, p)) / n
        excl = sum(g == q for g, q, o in zip(gold, p, res) if o) / sum(res)
        cont = [(g, q) for g, q, b in zip(gold, p, basis) if b == 'isi file']
        content = sum(g == q for g, q in cont) / len(cont) if cont else None
        cls = {}
        for c in sorted({g for g in gold if g != UNRES} | set(p)):
            tp = sum(g == c and q == c for g, q in zip(gold, p)); fp = sum(g != c and q == c for g, q in zip(gold, p)); fn = sum(g == c and q != c for g, q in zip(gold, p))
            nref = sum(g == c for g in gold)
            cls[c] = {'n_ref': nref, 'tp': tp, 'fp': fp, 'fn': fn, 'P': tp / (tp + fp) if tp + fp else None, 'R': tp / (tp + fn) if tp + fn else None}
        d = {'strict': strict, 'excl': excl, 'n_excl': sum(res), 'content_only': content, 'n_content': len(cont), 'classes': cls}
        if col == 'OS':
            nums = {'strict': strict, 'excl': excl}
            if content is not None: nums['content_only'] = content
            small = []
            for c in ('windows', 'macos', 'linux'):
                nums['P_' + c] = cls[c]['P']; nums['R_' + c] = cls[c]['R']
                if cls[c]['n_ref'] < 30: small.append(c)
            nums = {a: b for a, b in nums.items() if b is not None}
            name, val = min(nums.items(), key=lambda kv: kv[1])
            d['gate'] = {'numbers': nums, 'strictest': [name, val], 'passes_95': val >= 0.95 and not small, 'n_kecil': small}
        out[col][k] = d
json.dump(out, open(sys.argv[2], 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
f = lambda x: 'n/a' if x is None else '%.3f' % x
for col in ('OS', 'arch', 'type'):
    print('==', col, out[col]['basis_counts'])
    for k in CLF:
        d = out[col][k]; print('  %-9s strict %s | excl %s (n=%d) | content-only %s (n=%d)' % (k, f(d['strict']), f(d['excl']), d['n_excl'], f(d['content_only']), d['n_content']))
        if col == 'OS': print('      gate strictest', d['gate']['strictest'], 'passes', d['gate']['passes_95'], 'n_kecil', d['gate']['n_kecil'])
        print('      ', ' '.join('%s(n%d) P%s/R%s' % (c, v['n_ref'], f(v['P']), f(v['R'])) for c, v in d['classes'].items() if v['n_ref'] or v['fp']))
