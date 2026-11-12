import json,pathlib,urllib.request,urllib.error
T=open(pathlib.Path.home()/'.gh_token').read().strip(); D=pathlib.Path(__file__).resolve().parent.parent/'data'
cov=json.load(open(D/'coverage_by_repo.json'))
todo=[r for r,v in cov.items() if v.get('cause')]
for r in todo:
    q=urllib.request.Request(f'https://api.github.com/repos/{r}/releases?per_page=10',headers={'Authorization':'Bearer '+T,'Accept':'application/vnd.github+json','User-Agent':'feasibility-study'})
    try:
        with urllib.request.urlopen(q,timeout=30) as f: b=f.read()
    except urllib.error.HTTPError as e: b=e.read()
    (D/'raw_secondary'/(r.replace('/','__')+'.json')).write_bytes(b)
print(len(todo))
