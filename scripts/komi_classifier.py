"""komi-store asset rules translated to Python, for comparison only.
DERIVATIVE WORK of komi-store/komi-store (Apache License 2.0; full text in third_party/komi-store/LICENSE; the repo has no NOTICE file).
Source: https://github.com/komi-store/komi-store  commit 19eb74474f5f45a63cca45fc1dc9b8f7314687f0
  core/domain/src/commonMain/kotlin/zed/rainxch/core/domain/utils/AssetPlatform.kt            lines 5-52  (assetPlatformOf, isAndroidApk)
  core/domain/src/commonMain/kotlin/zed/rainxch/core/domain/utils/AssetArchitectureMatcher.kt lines 14-65, 110 (token lists, matchArchitecture, boundary)
  core/data/src/jvmMain/kotlin/zed/rainxch/core/data/services/DesktopInstaller.kt             lines 74-97 (extension whitelist)
CHANGED: translated from Kotlin to Python; results remapped to this project's (os, arch, type) vocabulary. No upstream code is used verbatim.
Mapping choices (ours, not theirs):
  arch Known(X86_64)->x64, AARCH64->arm64, X86->x86, ARM->arm32; Universal via token->universal;
  Universal via 'no token at all' (their else-branch)->unknown; Foreign->unknown.
  type: 'installer' if the name ends in a whitelisted desktop/android extension, else 'not_installer'.
  komi has no portable/ambiguous class and does not install archives; assetPlatformOf returns null for zip/tar/msix/appx.
Their macOS 'universal/darwin' override (DesktopInstaller 371-380) is install-time compatibility, not classification: not ported.
classify()          = 'as ported' (arch is computed for every file name, as the Kotlin function does)
classify_pipeline() = pipeline-equivalent: komi evaluates arch only after the extension whitelist, so non-whitelisted names get
                      unknown/unknown (the same convention as this project's not_installer rows)."""
import re


def _b(*t):
    return re.compile(r'(^|[^a-z0-9])(' + '|'.join(t) + r')([^a-z0-9]|$)')


UNIV = _b('universal', 'noarch', 'all-arch', 'fat')
X64 = _b(r'x86[_-]64', 'amd64', 'win64', 'x64')
A64 = _b('aarch64', 'arm64', 'arm64-v8a', 'armv8a', 'armv8l', 'armv8', 'arm-v8', 'v8a')
X86 = _b('i386', 'i586', 'i686', 'ia32', 'win32', 'x86', '386')
ARM = _b('armeabi-v7a', 'armeabi', 'armv7l', 'armv7a', 'armv7', 'armv6l', 'armv6', 'armhf', 'armel', 'arm-v7', 'arm32', 'v7a', 'arm')
ALPINE = _b('linux', 'amd64', '386', 'armhf', 'armel', 'armv7l', 'armv6l', 'arm32', 'riscv64', 'riscv', 's390x', 'ppc64le', 'ppc64', 'powerpc', 'mips64', 'mips', 'loong64', 'loongarch', 'sparc64', 'sparc')
INSTALLABLE = ('.apk', '.exe', '.msi', '.dmg', '.pkg', '.appimage', '.deb', '.rpm', '.pkg.tar.zst')


def classify(name):
    lo = name.lower()
    if lo.endswith('.apk'):
        os_ = 'linux' if ALPINE.search(lo) else 'android'
    elif lo.endswith('.ipa'): os_ = 'ios'
    elif lo.endswith(('.exe', '.msi')): os_ = 'windows'
    elif lo.endswith(('.dmg', '.pkg')): os_ = 'macos'
    elif lo.endswith(('.deb', '.rpm', '.appimage', '.pkg.tar.zst', '.snap', '.flatpakref')): os_ = 'linux'
    else: os_ = 'unknown'
    n = lo.replace('_', '-')
    if UNIV.search(n): arch = 'universal'
    elif X64.search(n): arch = 'x64'
    elif A64.search(n): arch = 'arm64'
    elif X86.search(n): arch = 'x86'
    elif ARM.search(n): arch = 'arm32'
    else: arch = 'unknown'   # includes Foreign and the no-token Universal case
    typ = 'installer' if lo.endswith(INSTALLABLE) else 'not_installer'
    return (os_, arch, typ)


def classify_pipeline(name):
    o, a, t = classify(name)
    return (o, a, t) if t == 'installer' else ('unknown', 'unknown', 'not_installer')
