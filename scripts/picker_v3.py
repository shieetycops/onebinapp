"""picker_v3: name-only button picker for round 3. Hash-locked together with classifier_v3.py (see data/round3/LOCK.md).
Cells: (os, arch). Strict candidates ONLY: windows .exe(setup/installer by name) .msi .msix/.appx(+bundle); macos .dmg .pkg; linux .AppImage.
Silence rules (the picker returns None rather than guess):
  S1 helper names (uninstall, updater, vc_redist, redistributable, legacy, debug, cli, runtime, driver) are never candidates.
  S2 an .exe that is not clearly a setup (name has 'portable', or no setup/install token) is not a candidate (ambiguous exe).
  S3 cross-arch is never offered (no WOW64/Rosetta/emulation offers). Exact arch beats universal.
  S4 unknown-arch candidate is offered only if NO candidate for that OS in the release carries any arch token AND exactly one candidate remains.
  S5 several candidates in the best tier: choose by extension preference; if still more than one with the same extension, stay silent (variant tie).
COMPAT (used only by the evaluation, not by the picker): which asset arch runs on a cell's machine."""
import re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import classifier_v3 as C

STRICT_EXT = {'windows': ('.msi', '.msix', '.appx', '.msixbundle', '.appxbundle', '.exe'), 'macos': ('.dmg', '.pkg'), 'linux': ('.appimage',)}
PREF = {'windows': ['exe', 'msi', 'msix', 'appx'], 'macos': ['dmg', 'pkg'], 'linux': ['appimage']}
HELPER = re.compile(r'(^|[^a-z0-9])(uninstall(er)?|updater?|vc[-_]?redist|redistributables?|legacy|debug|cli|runtime|driver)([^a-z0-9]|$)')
COMPAT = {('windows', 'x64'): {'x64', 'x86', 'universal'}, ('windows', 'arm64'): {'arm64', 'x64', 'x86', 'universal'},
          ('macos', 'arm64'): {'arm64', 'universal', 'x64'}, ('macos', 'x64'): {'x64', 'universal'},
          ('linux', 'x64'): {'x64'}, ('linux', 'arm64'): {'arm64'}}
GATED_CELLS = [('windows', 'x64'), ('macos', 'arm64'), ('macos', 'x64'), ('linux', 'x64')]


def ext_kind(name):
    n = name.lower()
    for e in ('.msixbundle', '.appxbundle', '.msix', '.appx', '.msi', '.dmg', '.pkg', '.appimage', '.exe'):
        if n.endswith(e):
            return {'.msixbundle': 'msix', '.msix': 'msix', '.appxbundle': 'appx', '.appx': 'appx'}.get(e, e[1:])
    return None


def candidates(names, os_):
    """strict candidates for an OS: list of (name, ext_kind, arch). Uses classifier_v3 for OS/arch/type."""
    out = []
    for nm in names:
        k = ext_kind(nm)
        if not k or k not in PREF[os_]:
            continue
        o, a, t = C.classify(nm)
        if o != os_ or t == 'not_installer':
            continue
        if HELPER.search(nm.lower().replace('_', '-')):
            continue
        if k == 'exe' and (t != 'installer' or 'portable' in nm.lower()):
            continue
        out.append((nm, k, a))
    return out


def pick(names, os_, arch):
    cs = candidates(names, os_)
    if not cs:
        return None
    exact = [c for c in cs if c[2] == arch]
    univ = [c for c in cs if c[2] == 'universal']
    tier = exact or univ
    if not tier:
        known = [c for c in cs if c[2] != 'unknown']
        unk = [c for c in cs if c[2] == 'unknown']
        if known or len(unk) != 1:
            return None
        return unk[0][0]
    best = sorted(tier, key=lambda c: PREF[os_].index(c[1]))
    top = [c for c in best if c[1] == best[0][1]]
    return top[0][0] if len(top) == 1 else None
