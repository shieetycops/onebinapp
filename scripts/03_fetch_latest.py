"""Fetch raw GET /repos/{o}/{r}/releases/latest for every repo. Saves body bytes AS RECEIVED + headers + log row."""
import json, pathlib, time, urllib.request, urllib.error, datetime, concurrent.futures as cf
T = open(pathlib.Path.home()/'.gh_token').read().strip()
D = pathlib.Path(__file__).resolve().parent.parent/'data'; RAW = D/'raw'; RAW.mkdir(exist_ok=True)
repos = json.load(open(D/'repos.json',encoding='utf-8'))
def one(r):
    name = r['repo']; key = name.replace('/','__')
    req = urllib.request.Request(f'https://api.github.com/repos/{name}/releases/latest',
        headers={'Authorization':'Bearer '+T,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'feasibility-study'})
    ts = datetime.datetime.utcnow().isoformat()+'Z'
    try:
        with urllib.request.urlopen(req, timeout=30) as f: status, body, hdr = f.status, f.read(), f.headers
    except urllib.error.HTTPError as e: status, body, hdr = e.code, e.read(), e.headers
    except Exception as e: return {'repo':name,'status':'ERR','error':str(e),'fetched_at':ts}
    (RAW/f'{key}.json').write_bytes(body)
    (RAW/f'{key}.headers.txt').write_text(''.join(f'{k}: {v}\n' for k,v in hdr.items()), encoding='utf-8')
    return {'repo':name,'status':status,'bytes':len(body),'fetched_at':ts,'remaining':hdr.get('x-ratelimit-remaining')}
with cf.ThreadPoolExecutor(6) as ex: log = list(ex.map(one, repos))
json.dump(log, open(D/'fetch_log.json','w'), indent=1)
from collections import Counter; print(Counter(l['status'] for l in log)); print('last remaining', log[-1].get('remaining'))
