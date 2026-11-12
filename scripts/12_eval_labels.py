"""Usage: python scripts/12_eval_labels.py data/labels_todo.csv  (after the user fills OS/arch/type). Prints P/R per field/class + wrong cases."""
import sys,csv,collections,pathlib; sys.path.insert(0,str(pathlib.Path(__file__).parent)); from classifier import classify
rows=list(csv.DictReader(open(sys.argv[1] if len(sys.argv)>1 else 'data/labels_todo.csv',encoding='utf-8-sig')))
rows=[r for r in rows if r['type'].strip()]; print('labeled rows',len(rows),'of 100')
if len(rows)<100: print('WARNING incomplete labels')
wrong=[]
for field,idx in (('OS',0),('arch',1),('type',2)):
    gold=[r[field if field!='OS' else 'OS'].strip().lower() for r in rows]; pred=[classify(r['asset_name'])[idx] for r in rows]
    acc=sum(g==p for g,p in zip(gold,pred))/len(rows); print(f'\n== {field}: accuracy {acc:.3f}')
    for c in sorted(set(gold)|set(pred)):
        tp=sum(g==c and p==c for g,p in zip(gold,pred)); fp=sum(g!=c and p==c for g,p in zip(gold,pred)); fn=sum(g==c and p!=c for g,p in zip(gold,pred))
        P=tp/(tp+fp) if tp+fp else float('nan'); R=tp/(tp+fn) if tp+fn else float('nan'); print(f'  {c:14} P={P:.2f} R={R:.2f}  (tp{tp} fp{fp} fn{fn})')
    for r,g,p in zip(rows,gold,pred):
        if g!=p: wrong.append((field,r['repo'],r['asset_name'],g,p))
# installer-vs-not and "click-ready" (strict) as the headline
print('\nWRONG CASES (field, repo, asset, gold, predicted):'); [print(' ',w) for w in wrong]
