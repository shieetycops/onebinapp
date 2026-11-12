import sys,json,re,pathlib,random,collections,urllib.request,urllib.error; sys.path.insert(0,str(pathlib.Path(__file__).parent)); from classifier import *
D=pathlib.Path(__file__).resolve().parent.parent/'data'; T=open(pathlib.Path.home()/'.gh_token').read().strip()
cov=json.load(open(D/'coverage_by_repo.json')); n=0; dig=0; picked=[]; stable=0; withpick=0; sidecar=0
for repo,v in cov.items():
    f=D/'raw'/(repo.replace('/','__')+'.json')
    if v.get('cause'): continue
    j=json.loads(f.read_bytes()); A={a['name']:a for a in j['assets']}; names=set(A)
    for a in A.values(): n+=1; dig+= bool(a.get('digest'))
    ps={c['asset'] for c in v['cells'].values()}
    if ps: withpick+=1
    # stable-name test for /releases/latest/download/<name>: name contains no version (tag w/o v, or tag)
    tag=(j.get('tag_name') or ''); ver=tag.lstrip('vV')
    if ps and all(ver not in p for p in ps if ver): stable+=1
    for p in ps: picked.append((repo,p,A[p].get('digest')))
    if any((p+s) in names for p in ps for s in('.sha256','.sig','.asc','.sha256sum','.minisig')): sidecar+=1
print(f'assets in ok repos {n}; with digest field {dig} ({dig/n*100:.1f}%)')
print(f'repos with picked installer {withpick}; stable (version-free) installer names: {stable} ({stable/withpick*100:.1f}%); has sidecar checksum/sig for picked: {sidecar}')
rnd=random.Random(7); rep=sorted({r for r,_,_ in picked}); rnd.shuffle(rep); S=rep[:40]; res=collections.Counter(); det=[]
for r in S:
    d=next((dg for rr,p,dg in picked if rr==r and dg),None)
    if not d: res['no_digest_to_look_up']+=1; continue
    q=urllib.request.Request(f'https://api.github.com/repos/{r}/attestations/{d}',headers={'Authorization':'Bearer '+T,'Accept':'application/vnd.github+json','User-Agent':'feasibility-study'})
    try:
        with urllib.request.urlopen(q,timeout=30) as f: j=json.load(f); k='has_attestation' if j.get('attestations') else 'api_ok_empty'
    except urllib.error.HTTPError as e: k=f'http_{e.code}'
    res[k]+=1; det.append((r,k))
print('attestation sample (40 repos, 1 installer each):',dict(res))
json.dump({'attest':det,'stable_name_pct':stable/withpick,'digest_pct':dig/n},open(D/'trust_measure.json','w'))
