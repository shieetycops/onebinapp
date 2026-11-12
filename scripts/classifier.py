import re
CHK = re.compile(r'\.(sig|asc|sha\d*|sha\d+sum|md5|blockmap|yml|yaml|json|txt|zsync|png|jpg|md|hdiff|js|sbom|spdx|pem|cer|nupkg|minisig|intoto\.jsonl|sigstore)$|checksums?|sha256sums?|latest.*\.ya?ml|symbols?|\.pdb$|debug|-src|source|\bsrc\b', re.I)
def classify(name):
    n = name.lower()
    if CHK.search(n) or n.endswith(('.zip.sig',)) or re.search(r'(source|src)[-_.]?(code)?\.(zip|tar\.gz|tgz)$', n): return ('unknown','unknown','not_installer')
    # OS
    if n.endswith('.apk') or n.endswith('.aab'): os_='android'
    elif n.endswith('.ipa'): os_='ios'
    elif n.endswith(('.dmg','.pkg')) or re.search(r'mac(os)?|osx|darwin|apple|\.app\.zip', n): os_='macos'
    elif n.endswith(('.exe','.msi','.msix','.appx','.msixbundle','.appxbundle')) or re.search(r'win(dows|32|64|-)?|win_|\.win', n): os_='windows'
    elif n.endswith(('.appimage','.deb','.rpm','.snap','.flatpak','.pacman','.pkg.tar.zst','.ddeb')) or re.search(r'linux|ubuntu|debian|fedora|appimage|\.freebsd|bsd', n): os_='linux'
    else: os_='unknown'
    # arch
    if re.search(r'arm64|aarch64|arm64e|armv8', n): arch='arm64'
    elif re.search(r'armv7|armhf|arm32|armv6', n): arch='arm32'
    elif re.search(r'universal|\buniv\b', n): arch='universal'
    elif re.search(r'x86[-_]64|x64|amd64|win64|64[-_]?bit|x86_64', n): arch='x64'
    elif re.search(r'ia32|i386|i686|x86|win32|32[-_]?bit', n): arch='x86'
    else: arch='unknown'
    # type
    if n.endswith(('.msi','.msix','.appx','.msixbundle','.appxbundle','.dmg','.pkg','.appimage','.deb','.rpm','.snap','.flatpak','.apk','.ipa','.ddeb','.pacman','.pkg.tar.zst')): typ='installer'
    elif n.endswith('.exe'):
        if re.search(r'portable', n): typ='portable'
        elif re.search(r'setup|install|inst', n): typ='installer'
        else: typ='ambiguous'
    elif n.endswith(('.zip','.7z','.tar.gz','.tgz','.tar.xz','.tar.bz2','.tar.zst','.gz')):
        typ='portable' if os_!='unknown' else 'not_installer'
    else: typ='not_installer'
    if typ=='not_installer': os_,arch='unknown','unknown'
    return (os_,arch,typ)
def kind(name):
    """fine-grained kind used by picker"""
    n=name.lower(); os_,arch,typ=classify(name)
    if typ=='not_installer': return None
    for e in ('.appimage','.msi','.msix','.appx','.dmg','.pkg','.deb','.rpm','.flatpak','.snap'):
        if n.endswith(e): return (os_,arch,e[1:])
    if n.endswith('.exe'): return (os_,arch,'exe-installer' if typ=='installer' else 'exe-ambiguous' if typ=='ambiguous' else 'exe-portable')
    if typ=='portable': return (os_,arch,'zip')
    return None
PREF = {'windows':['exe-installer','msi','msix','appx','exe-ambiguous','exe-portable','zip'],
        'macos':['dmg','pkg','zip'], 'linux':['appimage','deb','rpm','flatpak','snap','zip']}
STRICT = {'windows':{'exe-installer','msi','msix','appx'},'macos':{'dmg','pkg'},'linux':{'appimage'}}
def pick(assets, os_, arch):
    """assets: list of names -> best asset name for (os,arch) or None. arch in x64/arm64"""
    best=None
    for a in assets:
        k=kind(a)
        if not k or k[0]!=os_ or k[2] not in PREF[os_]: continue
        ka=k[1]
        if ka==arch: ar=0
        elif ka in('universal','any'): ar=1
        elif ka=='unknown' and not (os_=='windows' and arch=='arm64'): ar=2
        else: continue
        score=(ar, PREF[os_].index(k[2]))
        if best is None or score<best[0]: best=(score,a)
    return best[1] if best else None
