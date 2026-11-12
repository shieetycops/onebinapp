"""Download the 30-file dmg/pkg sample (data/round3/dmg_pkg_sample.json) in full, one new empty dir per file under SCRATCH,
open with 7-Zip 21.04, read Mach-O arch of the main executable (dmg) or xar hostArchitectures / Mach-O in payload (pkg).
Nothing is executed. Unopenable -> 'tidak bisa dibuka' with a reason, never guessed.
Run: python -I scripts/20_dmg_pkg_sample.py <SCRATCH_DIR>   -> data/round3/dmg_pkg_sample_result.json"""
import json, sys, pathlib, subprocess, struct, plistlib, re, urllib.request, shutil, os, zlib, concurrent.futures as cf
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import picker_v3 as P
D = HERE.parent / 'data' / 'round3'
SCR = pathlib.Path(sys.argv[1]); SCR.mkdir(parents=True, exist_ok=True)
SZ = r'C:\WINDOWS\system32\7z.exe'
CPU = {0x01000007: 'x64', 0x0100000C: 'arm64', 7: 'x86', 12: 'arm32'}
UNOPEN = 'tidak bisa dibuka'


def macho(path):
    with open(path, 'rb') as f: h = f.read(4096)
    if len(h) < 8: return None
    if h[:4] in (b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
        n = struct.unpack('>I', h[4:8])[0]
        if n > 8: return None
        step = 20 if h[:4] == b'\xca\xfe\xba\xbe' else 32
        ar = {CPU.get(struct.unpack('>I', h[8 + i * step:12 + i * step])[0], 'other') for i in range(n)}
        return ('universal' if {'x64', 'arm64'} <= ar else (ar.pop() if len(ar) == 1 else 'multi:' + ','.join(sorted(ar))))
    if h[:4] in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe'):
        return CPU.get(struct.unpack('<I', h[4:8])[0], 'other')
    return None


def sz(*a):
    return subprocess.run([SZ, *a], capture_output=True, text=True, timeout=1800)


def analyse_dmg(d, f):
    r = sz('x', '-y', '-o' + str(d / 'x'), str(f), '-ir!*Contents\MacOS\*', '-ir!*Contents\Info.plist')
    root = d / 'x'
    plists = sorted([p for p in root.rglob('Contents/Info.plist') if (p.parent / 'MacOS').is_dir()], key=lambda p: len(p.parts)) if root.exists() else []
    if not plists:
        return None, 'no .app extracted by 7-Zip 21.04 (exit %s): %s' % (r.returncode, (r.stdout + r.stderr).strip().splitlines()[-1:] or '')
    p0 = plists[0]; exe = None
    try: exe = plistlib.loads(p0.read_bytes()).get('CFBundleExecutable')
    except Exception: pass
    mdir = p0.parent / 'MacOS'
    cand = [mdir / exe] if exe and (mdir / exe).exists() else []
    basis = 'CFBundleExecutable'
    if not cand:
        cand = sorted([x for x in mdir.glob('*') if x.is_file()], key=lambda x: -x.stat().st_size)[:1]; basis = 'largest file in MacOS (no usable CFBundleExecutable)'
    if not cand: return None, 'no executable in MacOS dir'
    a = macho(cand[0])
    return (a, basis + ': ' + cand[0].name) if a else (None, 'not Mach-O: ' + cand[0].name)


def analyse_pkg(d, f):
    b = f.read_bytes()
    if b[:4] != b'xar!': return None, 'not xar'
    hl, = struct.unpack('>H', b[4:6]); clen, = struct.unpack('>Q', b[8:16])
    toc = zlib.decompress(b[hl:hl + clen]).decode('utf-8', 'replace')
    m = re.search(r'hostArchitectures="([^"]+)"', toc)
    heap = b[hl + clen:]
    # hostArchitectures usually lives in Distribution (xml in heap); scan the heap names via 7z listing + extraction
    r = sz('x', '-y', '-o' + str(d / 'x'), str(f))
    txt = ''
    for p in (d / 'x').rglob('*'):
        if p.is_file() and p.name in ('Distribution', 'PackageInfo'):
            txt += p.read_text(errors='replace')
    hm = re.findall(r'hostArchitectures="([^"]+)"', txt)
    if hm:
        s = set(','.join(hm).replace(' ', '').split(','))
        a = {'x86_64': 'x64', 'arm64': 'arm64', 'i386': 'x86'}
        ar = {a.get(x, x) for x in s}
        return ('universal' if {'x64', 'arm64'} <= ar else ('+'.join(sorted(ar)))), 'xar hostArchitectures=' + ','.join(sorted(s))
    # fallback: Mach-O inside the payload (gzip cpio) -- two more 7-Zip passes
    for pl in list((d / 'x').rglob('Payload')):
        if pl.is_file():
            y = pl.parent / 'p1'
            sz('x', '-y', '-o' + str(y), str(pl))
            for inner in list(y.glob('*')):
                if inner.is_file():
                    sz('x', '-y', '-o' + str(y / 'p2'), str(inner))
    cand = []
    for x in (d / 'x').rglob('*'):
        if x.is_file() and x.stat().st_size > 4096 and x.parent.name != 'p1':
            a = macho(x)
            if a: cand.append((x.stat().st_size, a, x))
    if cand:
        cand.sort(key=lambda c: -c[0])
        return cand[0][1], 'no hostArchitectures; largest Mach-O in payload: ' + cand[0][2].name
    return None, 'no hostArchitectures and no Mach-O found in payload (7-Zip exit %s)' % r.returncode


def one(it):
    key = it['key']; name = key.split('|', 1)[1]
    d = SCR / re.sub(r'[^A-Za-z0-9._-]', '_', key)
    if d.exists(): shutil.rmtree(d)
    d.mkdir(parents=True)
    f = d / name
    try:
        req = urllib.request.Request(it['url'], headers={'User-Agent': 'feasibility-study'})
        with urllib.request.urlopen(req, timeout=300) as r, open(f, 'wb') as o: shutil.copyfileobj(r, o)
    except Exception as e:
        return dict(it, status=UNOPEN, arch=None, note='download failed: %s' % e)
    try:
        a, note = (analyse_pkg if name.lower().endswith('.pkg') else analyse_dmg)(d, f)
    except Exception as e:
        a, note = None, 'analysis error: %s' % e
    res = dict(it, size=f.stat().st_size, status='dibaca' if a else UNOPEN, arch=a, note=note)
    if a:
        res['wrong_for_cells'] = [c for c in it['cells_offered'] if a not in ('universal',) and a not in P.COMPAT[('macos', c)] and not (a.startswith('multi:') or a == 'other')]
        res['wrong'] = bool(res['wrong_for_cells'])
    return res


items = json.load(open(D / 'dmg_pkg_sample.json'))['items']
with cf.ThreadPoolExecutor(3) as e: res = list(e.map(one, items))
read = [r for r in res if r['status'] == 'dibaca']
wrong = [r for r in res if r.get('wrong')]
out = {'n_sample': len(res), 'n_read': len(read), 'n_unopened': len(res) - len(read), 'n_wrong': len(wrong),
       'error_rate': (len(wrong) / len(read)) if read else None, 'macos_fails_by_sample': bool(read and len(wrong) / len(read) > 0.02), 'items': res}
json.dump(out, open(D / 'dmg_pkg_sample_result.json', 'w'), indent=1, ensure_ascii=False)
print({k: v for k, v in out.items() if k != 'items'})
for r in res: print(r['status'], r['arch'], r.get('wrong'), r['key'], '|', r['note'])
