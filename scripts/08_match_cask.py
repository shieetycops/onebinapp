import sys,json,re,pathlib,collections; sys.path.insert(0,str(pathlib.Path(__file__).parent)); from classifier import *
D=pathlib.Path(__file__).resolve().parent.parent/'data'
cask=json.loads((D/'ext'/'cask.json').read_bytes()); cov=json.load(open(D/'coverage_by_repo.json'))
by={}
GH=re.compile(r'https?://github\.com/([^/]+/[^/]+)/(?:releases/download|releases/latest/download|raw|archive)/(.*)',re.I)
for c in cask:
    u=c.get('url') or ''; m=GH.match(u)
    if m: by.setdefault(m.group(1).lower(),[]).append((c['token'],u,m.group(2).split('/')[-1],c.get('version')))
    else:
        h=c.get('homepage') or ''; m2=re.match(r'https?://github\.com/([^/]+/[^/#?]+)',h,re.I)
        if m2: by.setdefault(m2.group(1).lower(),[]).append((c['token'],u,u.split('/')[-1].split('?')[0],c.get('version')))
def norm(n,ver=None):
    n=n.lower()
    if ver: n=n.replace(str(ver).lower(),'{v}').replace('v'+str(ver).lower(),'{v}')
    n=re.sub(r'v?\d+(\.\d+){1,3}([-+.]\w+)?','{v}',n); return n
rows=[]; cnt=collections.Counter()
inCask=[r for r in cov if r.lower() in by]
print('repos in cask (by github url/homepage):',len(inCask),'of',len(cov))
for r in inCask:
    for tok,u,base,ver in by[r.lower()]:
        gh=bool(re.match(r'https?://github\.com/',u,re.I))
        v=cov[r]; cells=v.get('cells',{})
        if not gh: cnt['cask_url_off_github']+=1; rows.append((r,tok,'OFF_GITHUB',u)); continue
        if not cells: cnt['cask_on_github_but_our_latest_has_no_desktop_installer']+=1; rows.append((r,tok,'OUR_LATEST_EMPTY',base)); continue
        mac=[cells[k]['asset'] for k in('macos-arm64','macos-x64') if k in cells]
        mm=[a for a in mac if a.lower()==base.lower()]
        mn=[a for a in mac if norm(a,ver)==norm(base,ver)]
        ck=kind(base); same_ext=any(kind(a) and ck and kind(a)[2]==ck[2] for a in mac)
        lvl='exact' if mm else 'normalized' if mn else 'same_type_diff_name' if same_ext else 'mismatch'
        cnt[lvl]+=1; rows.append((r,tok,lvl,f'ours={mac} cask={base}'))
print(cnt)
json.dump(rows,open(D/'match_cask.json','w'),indent=1)
for x in rows:
    if x[2] in('mismatch','same_type_diff_name'): print(x)
