import sys,json,pathlib,collections; sys.path.insert(0,str(pathlib.Path(__file__).parent)); from classifier import *
D=pathlib.Path(__file__).resolve().parent.parent/'data'
log={l['repo']:l for l in json.load(open(D/'fetch_log.json'))}
res={}; out=collections.Counter()
for repo,l in log.items():
    f=D/'raw'/(repo.replace('/','__')+'.json')
    if l['status']==404: res[repo]={'cause':'404_no_release'}; continue
    j=json.loads(f.read_bytes()); names=[a['name'] for a in j.get('assets',[])]
    r={'tag':j.get('tag_name'),'n_assets':len(names),'prerelease':j.get('prerelease'),'cells':{}}
    if not names: r['cause']='zero_assets_source_only'
    for os_,archs in (('windows',('x64','arm64')),('macos',('arm64','x64')),('linux',('x64','arm64'))):
        for ar in archs:
            p=pick(names,os_,ar)
            if p: k=kind(p); r['cells'][f'{os_}-{ar}']={'asset':p,'kind':k[2],'strict':k[2] in STRICT[os_]}
    anyos={os_:any(c.startswith(os_) for c in r['cells']) for os_ in('windows','macos','linux')}
    r['any_os']=anyos
    if names and not r['cells']: r['cause']='assets_but_no_desktop_installer'
    res[repo]=r
json.dump(res,open(D/'coverage_by_repo.json','w'),indent=1)
N=len(res); print('N repos',N)
causes=collections.Counter(v.get('cause','ok') for v in res.values()); print(causes)
for os_,archs in (('windows',('x64','arm64')),('macos',('arm64','x64')),('linux',('x64','arm64'))):
    for ar in archs:
        k=f'{os_}-{ar}'; loose=sum(1 for v in res.values() if k in v.get('cells',{})); strict=sum(1 for v in res.values() if v.get('cells',{}).get(k,{}).get('strict'))
        print(f'{k:14} strict {strict/N*100:5.1f}%  loose {loose/N*100:5.1f}%')
    s=sum(1 for v in res.values() if any(c.get('strict') for kk,c in v.get('cells',{}).items() if kk.startswith(os_)))
    l=sum(1 for v in res.values() if v.get('any_os',{}).get(os_))
    print(f'  {os_} ANY-arch strict {s/N*100:.1f}% loose {l/N*100:.1f}%')
all3=sum(1 for v in res.values() if all(any(c.get('strict') for kk,c in v.get('cells',{}).items() if kk.startswith(o)) for o in('windows','macos','linux')))
w=sum(1 for v in res.values() if any(c.get('strict') for kk,c in v.get('cells',{}).items() if kk.startswith('windows')) or any(c.get('strict') for kk,c in v.get('cells',{}).items() if kk.startswith('macos')))
print('strict on all 3 OS',all3/N*100,'| strict on Win or mac',w/N*100)
