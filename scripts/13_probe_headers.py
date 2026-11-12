"""Step 1 of content-based labeling. For each asset in labels_todo.csv: HTTP Range request for the START of the file only,
then identify OS/arch from the BYTES (PE, ELF, Mach-O, xar .pkg, MSI/OLE, .deb control, .rpm header).
Format detection uses magic bytes only; the asset name is logged for reference and never used for decisions.
Unreadable -> 'tidak terbaca'.
Run: python -I scripts/13_probe_headers.py
Output: data/evidence/NNN.json (+ NNN.head.bin = first 64 KiB), data/evidence_summary.json"""
import csv, json, struct, zlib, lzma, io, re, tarfile, pathlib, collections
import urllib.request, urllib.error, concurrent.futures as cf
import zstandard

import os
D = pathlib.Path(os.environ['EVAL_DIR']) if os.environ.get('EVAL_DIR') else pathlib.Path(__file__).resolve().parent.parent / 'data'  # EVAL_DIR=data/clean for the clean sample
E = D / 'evidence'
E.mkdir(exist_ok=True)
UNR = 'tidak terbaca'
ALL = {r['repo'] + '|' + r['asset_name']: r for r in json.load(open(D / 'all_assets.json', encoding='utf-8'))}
todo = list(csv.DictReader(open(D / 'labels_todo.csv', encoding='utf-8-sig')))
N_DEFAULT = 512 * 1024
N_MSI = 4 * 1024 * 1024
OLE = bytes.fromhex('d0cf11e0a1b11ae1')


def fetch(url, n):
    req = urllib.request.Request(url, headers={'Range': 'bytes=0-%d' % (n - 1), 'User-Agent': 'feasibility-study'})
    try:
        with urllib.request.urlopen(req, timeout=60) as f:
            body = f.read(n)
            return f.status, f.headers.get('Content-Range'), body
    except urllib.error.HTTPError as e:
        return e.code, None, b''
    except Exception as e:
        return 'ERR', str(e), b''


PE_M = {0x8664: 'x64', 0xAA64: 'arm64', 0x14c: 'x86', 0x1c4: 'arm32', 0x1c0: 'arm32'}
ELF_M = {0x3E: 'x64', 0xB7: 'arm64', 0x28: 'arm32', 0x03: 'x86', 0xF3: 'riscv64', 0x15: 'ppc64', 0x16: 's390x'}
MACHO_CPU = {0x01000007: 'x64', 0x0100000C: 'arm64', 7: 'x86', 12: 'arm32'}
DEB_ARCH = {'amd64': 'x64', 'arm64': 'arm64', 'armhf': 'arm32', 'armel': 'arm32', 'i386': 'x86', 'all': 'any', 'riscv64': 'riscv64'}
RPM_ARCH = {'x86_64': 'x64', 'aarch64': 'arm64', 'armv7hl': 'arm32', 'i686': 'x86', 'i386': 'x86', 'noarch': 'any'}
MSI_ARCH = {'intel': 'x86', 'x64': 'x64', 'amd64': 'x64', 'intel64': 'x64', 'arm64': 'arm64', 'arm': 'arm32'}


def parse_pe(b):
    pe = struct.unpack_from('<I', b, 0x3C)[0]
    if pe + 6 <= len(b) and b[pe:pe + 4] == b'PE\0\0':
        m = struct.unpack_from('<H', b, pe + 4)[0]
        ev = {'format': 'PE', 'machine': hex(m), 'raw_hex': b[pe:pe + 6].hex()}
        ev['markers'] = [k.decode() for k in (b'Nullsoft', b'Inno Setup', b'WiX', b'MSIX', b'InstallShield') if k in b]
        return 'windows', PE_M.get(m, 'other(%s)' % hex(m)), ev
    return UNR, UNR, {'format': 'MZ without PE header in range'}


def parse_elf(b):
    cls, data, osabi = b[4], b[5], b[7]
    end = '<' if data == 1 else '>'
    etype, mach = struct.unpack_from(end + 'HH', b, 16)
    ev = {'format': 'ELF', 'class': cls, 'osabi': osabi, 'e_type': etype, 'e_machine': hex(mach), 'raw_hex': b[:20].hex()}
    os_ = 'linux' if osabi in (0, 3) else 'other-unix(osabi=%d)' % osabi
    return os_, ELF_M.get(mach, 'other(%s)' % hex(mach)), ev


def parse_deb(b):
    pos, ev = 8, {'format': 'ar (deb)', 'members': []}
    while pos + 60 <= len(b):
        name = b[pos:pos + 16].decode('latin1').strip()
        size = int(b[pos + 48:pos + 58].decode().strip() or 0)
        at = pos + 60
        ev['members'].append(name)
        if name.startswith('control.tar'):
            chunk = b[at:at + size]
            try:
                if name.endswith('.zst'):
                    raw = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(chunk)).read()
                elif name.endswith('.xz'):
                    raw = lzma.LZMADecompressor().decompress(chunk)
                elif name.endswith('.gz'):
                    raw = zlib.decompressobj(31).decompress(chunk)
                else:
                    raw = chunk
                with tarfile.open(fileobj=io.BytesIO(raw)) as t:
                    for m in t.getmembers():
                        if m.name.lstrip('./') == 'control':
                            ctl = t.extractfile(m).read().decode('utf-8', 'replace')
                            a = re.search(r'^Architecture:\s*(\S+)', ctl, re.M)
                            ev['control_Architecture'] = a.group(1) if a else None
                            ev['control_head'] = ctl[:300]
                            return 'linux', DEB_ARCH.get(ev['control_Architecture'], 'other(%s)' % ev['control_Architecture']), ev
            except Exception as e:
                ev['err'] = repr(e)
                return UNR, UNR, ev
            return UNR, UNR, ev
        pos = at + size + (size & 1)
    ev['err'] = 'control.tar not within fetched range'
    return UNR, UNR, ev


def parse_rpm(b):
    ev = {'format': 'RPM', 'lead_archnum': struct.unpack_from('>H', b, 8)[0]}
    pos = 96
    for hdr in range(2):  # signature header, then main header
        if b[pos:pos + 3] != b'\x8e\xad\xe8':
            ev['err'] = 'header magic missing'
            return UNR, UNR, ev
        nidx, hsz = struct.unpack_from('>II', b, pos + 8)
        idx_at = pos + 16
        data_at = idx_at + 16 * nidx
        if hdr == 1:
            for i in range(nidx):
                tag, typ, off, cnt = struct.unpack_from('>IIII', b, idx_at + 16 * i)
                if tag == 1022 and typ == 6:
                    s = b[data_at + off:b.index(b'\0', data_at + off)].decode()
                    ev['header_ARCH'] = s
                    return 'linux', RPM_ARCH.get(s, 'other(%s)' % s), ev
            ev['err'] = 'ARCH tag not found'
            return UNR, UNR, ev
        pos = data_at + hsz
        pos += (8 - pos % 8) % 8
    return UNR, UNR, ev


def parse_xar(b):
    hl, ver, toc_c, toc_u, alg = struct.unpack_from('>HHQQI', b, 4)
    ev = {'format': 'xar (.pkg)', 'hdr': hl, 'toc_compressed': toc_c}
    try:
        toc = zlib.decompress(b[hl:hl + toc_c]).decode('utf-8', 'replace')
    except Exception as e:
        ev['err'] = repr(e)
        return UNR, UNR, ev
    heap = hl + toc_c
    for blk in re.findall(r'<file id="\d+">.*?</file>', toc, re.S):
        if '<name>Distribution</name>' in blk:
            o = int(re.search(r'<offset>(\d+)', blk).group(1))
            ln = int(re.search(r'<length>(\d+)', blk).group(1))
            if heap + o + ln > len(b):
                ev['err'] = 'Distribution beyond fetched range'
                return 'macos', UNR, ev
            raw = b[heap + o:heap + o + ln]
            try:
                raw = zlib.decompress(raw)
            except Exception:
                pass
            t = raw.decode('utf-8', 'replace')
            h = re.search(r'hostArchitectures="([^"]+)"', t)
            ev['hostArchitectures'] = h.group(1) if h else None
            ev['distribution_head'] = t[:200]
            if not h:
                return 'macos', UNR, ev
            a = set(h.group(1).replace(' ', '').split(','))
            arch = 'universal' if {'x86_64', 'arm64'} <= a else 'x64' if a == {'x86_64'} else 'arm64' if a == {'arm64'} else 'other(%s)' % h.group(1)
            return 'macos', arch, ev
    ev['err'] = 'no Distribution file in TOC'
    return UNR, UNR, ev


def parse(b):
    if b[:2] == b'MZ' and len(b) > 0x40:
        return parse_pe(b)
    if b[:4] == b'\x7fELF':
        return parse_elf(b)
    magic = b[:4]
    if magic in (b'\xfe\xed\xfa\xce', b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe', b'\xcf\xfa\xed\xfe'):
        cpu = struct.unpack_from('>I' if magic[0] == 0xfe else '<I', b, 4)[0]
        return 'macos', MACHO_CPU.get(cpu, 'other(%s)' % hex(cpu)), {'format': 'Mach-O', 'cputype': hex(cpu), 'raw_hex': b[:12].hex()}
    if magic == b'\xca\xfe\xba\xbe' and len(b) >= 8:
        n = struct.unpack_from('>I', b, 4)[0]
        if 1 <= n <= 8:  # a Java class file has a version here (>=45), so this is fat Mach-O
            cpus = [struct.unpack_from('>I', b, 8 + 20 * i)[0] for i in range(n)]
            archs = sorted({MACHO_CPU.get(c, 'other(%s)' % hex(c)) for c in cpus})
            return 'macos', ('universal' if len(archs) > 1 else archs[0]), {'format': 'Mach-O fat', 'cputypes': [hex(c) for c in cpus], 'raw_hex': b[:8 + 20 * n].hex()}
    if b[:8] == b'!<arch>\n':
        return parse_deb(b)
    if magic == b'\xed\xab\xee\xdb':
        return parse_rpm(b)
    if magic == b'xar!':
        return parse_xar(b)
    if b[:8] == OLE:
        ev = {'format': 'OLE2 (MSI?)'}
        m = re.search(rb'(Intel64|Intel|x64|Arm64|ARM64|Arm|AMD64);[\d,]*\d', b)
        if m:
            ev['template'] = m.group(0).decode()
            return 'windows', MSI_ARCH[m.group(1).decode().lower()], ev
        ev['err'] = 'Template property not within fetched range'
        return UNR, UNR, ev
    if b[:4] == b'PK\x03\x04':
        nl, el = struct.unpack_from('<HH', b, 26)
        return UNR, UNR, {'format': 'ZIP', 'first_entry': b[30:30 + nl].decode('utf-8', 'replace'), 'note': 'zip header carries no OS/arch'}
    if b[:2] == b'\x1f\x8b':
        return UNR, UNR, {'format': 'gzip', 'note': 'compressed; not parsed'}
    if b[:6] == b'\xfd7zXZ\x00':
        return UNR, UNR, {'format': 'xz', 'note': 'compressed; not parsed'}
    if b[:6] == b'7z\xbc\xaf\x27\x1c':
        return UNR, UNR, {'format': '7z'}
    if b[:4] == b'hsqs':
        return UNR, UNR, {'format': 'squashfs'}
    if len(b) and all(c in b'\t\n\r' or 32 <= c < 127 or c >= 128 for c in b[:512]):
        return UNR, UNR, {'format': 'text', 'head': b[:80].decode('utf-8', 'replace'), 'note': 'text; states no OS/arch'}
    return UNR, UNR, {'format': 'unknown at file start', 'raw_hex': b[:16].hex()}


def one(i):
    r = todo[i]
    a = ALL[r['repo'] + '|' + r['asset_name']]
    st, cr, head = fetch(a['url'], N_DEFAULT)
    if st in (200, 206) and head[:8] == OLE and len(head) == N_DEFAULT:
        st, cr, head = fetch(a['url'], N_MSI)
    out = {'idx': i, 'repo': r['repo'], 'asset_name': r['asset_name'], 'http_status': st, 'content_range': cr, 'bytes_read': len(head)}
    if st not in (200, 206) or not head:
        out.update(content_os=UNR, content_arch=UNR, evidence={'format': 'fetch failed'})
    else:
        try:
            o, ar, ev = parse(head)
        except Exception as e:
            o, ar, ev = UNR, UNR, {'format': 'parser error', 'err': repr(e)}
        out.update(content_os=o, content_arch=ar, evidence=ev)
    (E / ('%03d.head.bin' % i)).write_bytes(head[:65536])
    (E / ('%03d.json' % i)).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    return out


with cf.ThreadPoolExecutor(6) as ex:
    res = list(ex.map(one, range(len(todo))))
json.dump(res, open(D / 'evidence_summary.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(collections.Counter(r['evidence'].get('format') for r in res))
print('OS readable', sum(r['content_os'] != UNR for r in res), 'arch readable', sum(r['content_arch'] != UNR for r in res), 'of', len(res))
print('http', collections.Counter(r['http_status'] for r in res))
