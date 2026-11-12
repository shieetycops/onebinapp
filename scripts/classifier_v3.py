"""classifier_v3 (= v2 + two regression fixes + bare-binary arch reader): merge of this project's classifier.py (portable class, not_installer filter) with token rules from komi-store.
DERIVATIVE WORK in part of komi-store/komi-store (Apache License 2.0; full text in third_party/komi-store/LICENSE; no NOTICE file).
Source: https://github.com/komi-store/komi-store  commit 19eb74474f5f45a63cca45fc1dc9b8f7314687f0
  core/domain/src/commonMain/kotlin/zed/rainxch/core/domain/utils/AssetArchitectureMatcher.kt lines 14-65, 110
  (boundary() token matcher, the token lists incl. armeabi/armeabi-v7a/v7a/armel/i586/noarch, and the check order universal>x64>arm64>x86>arm)
CHANGED: translated from Kotlin to Python and combined with this project's rules; classifier.py is untouched.
Not taken from komi: no-token=universal; the darwin/universal install-time override; extension-only OS.
Fixes vs classifier.py (known causes from the dev run, see report): word-boundary OS keywords (fixes 'win' in TwinDesk), 'debug' only as a whole token
(not 'debugger'), dbgsym denied, .app.tar.gz/.app.tar.xz recognised as macOS, archives with no OS word but an arch token or 'portable' are portable
(OS stays unknown) instead of not_installer, armeabi-v7a mapped to arm32. AppImage with no arch in the name stays unknown (name cannot tell).
v3 changes vs v2: (1) "linux" prefix tokens (linuxmusl, linux-musl) are Linux; (2) "source"/"src" only as whole tokens (sourcegit passes, "Source code.zip" still denied);
(3) bare_binary_arch(name) reads arch tokens from extensionless names the way komi does (not used by the picker: bare binaries are not strict candidates).
Rules written to be general; the 100 dev rows were seen while writing them, so they are DEV data, not gate evidence."""
import re


def _b(*t):
    return re.compile(r'(^|[^a-z0-9])(' + '|'.join(t) + r')([^a-z0-9]|$)')


CHK = re.compile(r'\.(sig|asc|sha\d*|sha\d+sum|md5|blockmap|yml|yaml|json|txt|zsync|png|jpg|md|hdiff|js|sbom|spdx|pem|cer|nupkg|minisig|intoto\.jsonl|sigstore)$|checksums?|sha256sums?|latest.*\.ya?ml|symbols?|\.pdb$|dbgsym|-src|source|\bsrc\b', re.I)
DEBUG = _b('debug')
UNIV = _b('universal', 'noarch', 'all-arch', 'fat', 'univ')
X64 = _b(r'x86[_-]64', 'amd64', 'win64', 'x64', r'64[_-]?bit')
A64 = _b('aarch64', 'arm64', 'arm64e', 'arm64-v8a', 'armv8a', 'armv8l', 'armv8', 'arm-v8', 'v8a')
X86 = _b('i386', 'i586', 'i686', 'ia32', 'win32', 'x86', '386', r'32[_-]?bit')
ARM = _b('armeabi-v7a', 'armeabi', 'armv7l', 'armv7a', 'armv7', 'armv6l', 'armv6', 'armhf', 'armel', 'arm-v7', 'arm32', 'v7a')
OS_MAC = _b('mac', 'macos', 'osx', 'darwin', 'apple')
OS_WIN = _b('win', 'windows', 'win32', 'win64')
OS_LIN = _b('linux', 'linuxmusl', 'linuxgnu', 'ubuntu', 'debian', 'fedora', 'appimage', 'freebsd', 'bsd')
ARCHIVE = ('.zip', '.7z', '.tar.gz', '.tgz', '.tar.xz', '.tar.bz2', '.tar.zst', '.gz')


def classify(name):
    n = name.lower()
    nn = n.replace('_', '-')
    if CHK.search(n) or DEBUG.search(nn) or re.search(r'(source|src)[-_.]?(code)?\.(zip|tar\.gz|tgz)$', n):
        return ('unknown', 'unknown', 'not_installer')
    if n.endswith(('.apk', '.aab')): os_ = 'android'
    elif n.endswith('.ipa'): os_ = 'ios'
    elif n.endswith(('.dmg', '.pkg')) or OS_MAC.search(nn) or re.search(r'\.app\.(zip|tar\.gz|tar\.xz|tgz)$', n): os_ = 'macos'
    elif n.endswith(('.exe', '.msi', '.msix', '.appx', '.msixbundle', '.appxbundle')) or OS_WIN.search(nn): os_ = 'windows'
    elif n.endswith(('.appimage', '.deb', '.rpm', '.snap', '.flatpak', '.pacman', '.pkg.tar.zst', '.ddeb')) or OS_LIN.search(nn): os_ = 'linux'
    else: os_ = 'unknown'
    if UNIV.search(nn): arch = 'universal'
    elif X64.search(nn): arch = 'x64'
    elif A64.search(nn): arch = 'arm64'
    elif X86.search(nn): arch = 'x86'
    elif ARM.search(nn): arch = 'arm32'
    else: arch = 'unknown'
    if n.endswith(('.msi', '.msix', '.appx', '.msixbundle', '.appxbundle', '.dmg', '.pkg', '.appimage', '.deb', '.rpm', '.snap', '.flatpak', '.apk', '.ipa', '.ddeb', '.pacman', '.pkg.tar.zst')): typ = 'installer'
    elif n.endswith('.exe'):
        typ = 'portable' if 'portable' in n else 'installer' if re.search(r'setup|install|inst', n) else 'ambiguous'
    elif n.endswith(ARCHIVE):
        typ = 'portable' if (os_ != 'unknown' or arch != 'unknown' or 'portable' in n) else 'not_installer'
    else: typ = 'not_installer'
    if typ == 'not_installer': os_, arch = 'unknown', 'unknown'
    return (os_, arch, typ)


def bare_binary_arch(name):
    """arch from name tokens for names with no recognised extension (komi-style reading); 'unknown' if none."""
    nn = name.lower().replace('_', '-')
    for rx, a in ((UNIV, 'universal'), (X64, 'x64'), (A64, 'arm64'), (X86, 'x86'), (ARM, 'arm32')):
        if rx.search(nn): return a
    return 'unknown'
