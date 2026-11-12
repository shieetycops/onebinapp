import sys,json,re,pathlib,collections; sys.path.insert(0,str(pathlib.Path(__file__).parent)); from classifier import *
D=pathlib.Path(__file__).resolve().parent.parent/'data'; W=D/'ext'/'winget-pkgs'/'manifests'; cov=json.load(open(D/'coverage_by_repo.json'))
def vkey(s): return [(0,int(x),'') if x.isdigit() else (1,0,x) for x in re.split(r'[.-]',s)]
pk={}
for f in W.rglob('*.installer.yaml'):
    pid=f.parent.parent.name+'.'+f.parent.name if False else None
    pk.setdefault(f.parent.parent,[]).append(f)   # package dir -> version files
by={}
for pdir,fs in pk.items():
    f=max(fs,key=lambda x:vkey(x.parent.name)); t=f.read_text(encoding='utf-8',errors='ignore')
    blocks=re.findall(r'-\s*Architecture:\s*(\S+)(.*?)(?=\n-\s*Architecture:|\Z)',t,re.S)
    ents=[]
    for arch,body in blocks:
        m=re.search(r'InstallerUrl:\s*(\S+)',body); ty=re.search(r'InstallerType:\s*(\S+)',body)
        if m: ents.append((arch.lower(),m.group(1),ty.group(1) if ty else None))
    if not ents:
        for m in re.finditer(r'InstallerUrl:\s*(\S+)',t): ents.append(('?',m.group(1),None))
    for a,u,ty in ents:
        m=re.match(r'https?://github\.com/([^/]+/[^/]+)/',u,re.I)
        key=m.group(1).lower() if m else None
        by.setdefault(key or '__off__'+pdir.name,[]).append((pdir.name,a,u,ver:=f.parent.name))
def norm(n):
    n=n.lower(); return re.sub(r'v?\d+(\.\d+){1,3}([-+.]\w+)?','{v}',n)
cnt=collections.Counter(); rows=[]; inW=0
off=collections.Counter()
for r,v in cov.items():
    ents=by.get(r.lower())
    if ents is None:
        # off-github: winget package whose publisher dir == owner but url not github?
        if any(k.startswith('__off__') and k.split('__off__')[1].lower()==r.split('/')[-1].lower() for k in by): cnt['winget_off_github']+=1
        continue
    inW+=1
    cells=v.get('cells',{})
    if not cells: cnt['our_latest_empty']+=1; rows.append((r,'OUR_EMPTY',[e[2] for e in ents][:2])); continue
    for arch_w,ours_k in (('x64','windows-x64'),('arm64','windows-arm64')):
        we=[e for e in ents if e[1]==arch_w]
        if not we or ours_k not in cells: continue
        ours=cells[ours_k]['asset']; base={e[2].split('/')[-1] for e in we}
        lvl='exact' if ours in base else 'normalized' if norm(ours) in {norm(b) for b in base} else 'same_type_diff_name' if (kind(ours) and any(kind(b) and kind(b)[2]==kind(ours)[2] for b in base)) else 'mismatch'
        cnt[f'{arch_w}:{lvl}']+=1; rows.append((r,arch_w,lvl,ours,sorted(base)[:2]))
print('repos with GitHub-hosted winget installer URL:',inW); print(cnt)
json.dump(rows,open(D/'match_winget.json','w'),indent=1)
for x in rows:
    if len(x)>3 and x[2] in('mismatch','same_type_diff_name'): print(str(x)[:210])
