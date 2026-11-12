"""Regression tests for classifier_v3 / picker_v3 from known dev cases. Run: python scripts/test_v3.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import classifier_v3 as C, picker_v3 as P
T = [('copilot-linuxmusl-arm64.tar.gz', 'linux'), ('sourcegit_2026.24.win-x64.zip', 'unknown'), ('TwinDesk-3.0.0-amd64.deb', 'linux'),
     ('ChatGPT-MJ_universal.app.tar.gz', 'macos'), ('rn-debugger-macos-x64.zip', 'macos'), ('Source code.zip', 'unknown'), ('foo-source.tar.gz', 'unknown')]
for n, os_ in T:
    got = C.classify(n)[0]; assert got == os_, (n, got, os_)
assert C.classify('OpenLess_2.0.1+build.20261016_armeabi-v7a.apk')[1] == 'arm32'
assert C.bare_binary_arch('officecli-linux-x64') == 'x64'
a = ['App-1.0-setup-x64.exe', 'App-1.0-setup-arm64.exe', 'App-1.0.msi', 'Uninstall-App.exe', 'vc_redist.x64.exe', 'App-1.0-portable.exe', 'App-1.0.dmg', 'App-1.0.AppImage']
assert P.pick(a, 'windows', 'x64') == 'App-1.0-setup-x64.exe'          # exact arch, exe over msi (msi has no arch token)
assert P.pick(['App.dmg'], 'macos', 'arm64') == 'App.dmg'              # sole untagged candidate
assert P.pick(['App-x64.dmg', 'App.dmg'], 'macos', 'arm64') is None    # S4: a sibling carries an arch token
assert P.pick(['App-x64.dmg'], 'macos', 'arm64') is None               # S3: no cross-arch (Rosetta) offers
assert P.pick(['a-x64-setup.exe', 'b-x64-setup.exe'], 'windows', 'x64') is None  # S5 variant tie
assert P.pick(['App-1.0.exe'], 'windows', 'x64') is None               # S2 ambiguous exe
print('all tests passed')
