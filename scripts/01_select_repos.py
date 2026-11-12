"""Select 300 popular open-source desktop-app repos. Rule is fixed BEFORE any /releases/latest fetch
(avoids selecting on 'has installer'). Output: data/repos.json, data/excluded.json"""
import json, re, time, urllib.request, urllib.parse, pathlib
T = open(pathlib.Path.home()/'.gh_token').read().strip()
D = pathlib.Path(__file__).resolve().parent.parent/'data'
TOPICS = ['desktop-app','electron','electron-app','tauri','qt','gtk','wxwidgets','avalonia','flutter-desktop',
          'desktop','windows-app','macos-app','linux-app','desktop-application','cross-platform-desktop','compose-desktop','tauri-app']
BAD_TOPICS = {'library','framework','sdk','awesome','awesome-list','boilerplate','template','starter','tutorial','api','cli','plugin',
              'react-component','ui-library','toolkit','engine','game-engine','kernel','operating-system','cheatsheet','list','collection','docs','documentation','book'}
BAD_NAME = re.compile(r'(awesome|boilerplate|template|starter|example|tutorial|cheat|^electron$|^tauri$|^flutter$|^qt|^gtk|^wxwidgets|^avalonia$|\.github\.io$|-docs$|^docs$)', re.I)
def get(url):
    r = urllib.request.Request(url, headers={'Authorization':'Bearer '+T,'Accept':'application/vnd.github+json','User-Agent':'feasibility-study'})
    with urllib.request.urlopen(r) as f: return json.load(f)
seen, excluded = {}, []
for tp in TOPICS:
    for page in (1,2,3):
        q = urllib.parse.quote(f'topic:{tp} stars:>1000 archived:false fork:false')
        try: j = get(f'https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=100&page={page}')
        except Exception as e: print('ERR',tp,page,e); break
        for it in j['items']: seen.setdefault(it['full_name'], it)
        time.sleep(2.2)
        if len(j['items'])<100: break
    print(tp, len(seen))
keep = []
for fn, it in sorted(seen.items(), key=lambda kv:-kv[1]['stargazers_count']):
    topics = set(it.get('topics') or [])
    why = None
    if topics & BAD_TOPICS: why = 'topic:'+','.join(sorted(topics & BAD_TOPICS))
    elif BAD_NAME.search(it['name']): why = 'name-pattern'
    elif it.get('is_template'): why = 'template'
    elif it.get('language') is None: why = 'no-language(likely docs/list)'
    if why: excluded.append({'repo':fn,'stars':it['stargazers_count'],'reason':why,'desc':it.get('description')})
    else: keep.append({'repo':fn,'stars':it['stargazers_count'],'language':it['language'],'topics':sorted(topics),'desc':it.get('description'),'html_url':it['html_url']})
json.dump(keep, open(D/'repos_all_candidates.json','w',encoding='utf-8'), indent=1, ensure_ascii=False)
json.dump(keep[:300], open(D/'repos.json','w',encoding='utf-8'), indent=1, ensure_ascii=False)
json.dump({'pool_size':len(seen),'kept_after_filter':len(keep),'excluded':excluded,'overflow':[k['repo'] for k in keep[300:]]}, open(D/'excluded.json','w',encoding='utf-8'), indent=1, ensure_ascii=False)
print('pool',len(seen),'keep',len(keep),'excluded',len(excluded))
