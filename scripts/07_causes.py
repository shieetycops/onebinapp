import sys,json,collections,pathlib; sys.path.insert(0,str(pathlib.Path(__file__).parent)); from classifier import *
D=pathlib.Path(__file__).resolve().parent.parent/'data'; cov=json.load(open(D/'coverage_by_repo.json')); out=collections.Counter(); det={}
for r,v in cov.items():
    if not v.get('cause'): continue
    rel=json.loads((D/'raw_secondary'/(r.replace('/','__')+'.json')).read_bytes())
    if not isinstance(rel,list) or not rel: b='no_releases_at_all'
    else:
        has=any(kind(a['name']) and kind(a['name'])[0] in('windows','macos','linux') for x in rel for a in x.get('assets',[]))
        b='recent_release_has_installer(monorepo/tag-order issue)' if has else ('only_prereleases' if all(x.get('prerelease') for x in rel) else 'none_in_last10')
    out[(v['cause'],b)]+=1; det[r]=b
for k,c in sorted(out.items()): print(k,c)
json.dump(det,open(D/'causes_secondary.json','w'),indent=1)
