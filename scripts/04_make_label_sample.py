"""Flatten all assets from raw payloads; draw 100 for HAND labeling (seed fixed, <=2 per repo). Sample is held out from classifier dev."""
import json, pathlib, random, csv
D = pathlib.Path(__file__).resolve().parent.parent/'data'
rows = []
for f in sorted((D/'raw').glob('*.json')):
    if f.name.endswith('.headers.txt'): continue
    try: j = json.loads(f.read_bytes())
    except Exception: continue
    if not isinstance(j, dict) or 'assets' not in j: continue
    repo = f.stem.replace('__','/',1)
    for a in j['assets']: rows.append({'repo':repo,'tag':j.get('tag_name'),'asset_name':a['name'],'size':a['size'],'url':a['browser_download_url']})
json.dump(rows, open(D/'all_assets.json','w',encoding='utf-8'), indent=0)
rnd = random.Random(20261111); rnd.shuffle(rows)
per, pick = {}, []
for r in rows:
    if per.get(r['repo'],0) >= 2: continue
    per[r['repo']] = per.get(r['repo'],0)+1; pick.append(r)
    if len(pick) == 100: break
json.dump([r['repo']+'|'+r['asset_name'] for r in pick], open(D/'heldout_ids.json','w'))
with open(D/'labels_todo.csv','w',newline='',encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['repo','asset_name','size','OS','arch','type'])
    for r in pick: w.writerow([r['repo'],r['asset_name'],r['size'],'','',''])
(D/'labels_guide.txt').write_text("""PANDUAN LABEL (isi kolom OS, arch, type; buka labels_todo.csv di Excel)
OS   : windows | macos | linux | android | ios | any | unknown
arch : x64 | arm64 | x86 | universal | any | unknown      (universal = macOS Intel+Apple Silicon sekaligus)
type : installer      = Windows .exe/.msi/.msix setup, macOS .dmg/.pkg, Linux .AppImage/.deb/.rpm/.flatpak/.snap -> klik lalu pasang
       portable       = zip/tar/7z berisi app jadi tanpa instal
       ambiguous      = tidak bisa dipastikan dari NAMA saja (mis. app.exe bisa setup atau portabel)
       not_installer  = checksum, signature, blockmap, latest*.yml, source code, symbols, debug, sbom, dokumen, dll
Isi berdasarkan NAMA FILE (dan ekstensi) saja, seperti yang dilihat calon pengguna. Jika OS/arch tidak tertulis, isi unknown.
""", encoding='utf-8')
print('total assets', len(rows), 'repos with assets', len({r['repo'] for r in rows}), 'sample', len(pick), 'repos in sample', len(per))
