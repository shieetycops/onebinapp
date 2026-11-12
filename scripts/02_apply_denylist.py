"""Manual curation pass: remove non-app repos (libs/frameworks/build tools/servers/themes/hardware) judged from NAME+DESCRIPTION only
(never from release contents). Refill from the stars-ordered overflow. Output data/repos.json (300), data/curation.json."""
import json, pathlib
D = pathlib.Path(__file__).resolve().parent.parent/'data'
L = lambda p: json.load(open(D/p, encoding='utf-8'))
sel = L('repos.json') if not (D/'repos_stage1.json').exists() else L('repos_stage1.json')
if not (D/'repos_stage1.json').exists(): json.dump(sel, open(D/'repos_stage1.json','w',encoding='utf-8'), indent=1, ensure_ascii=False)
ex = L('excluded.json')
DENY = {  # repo -> reason
 'microsoft/playwright':'testing framework','PanJiaChen/vue-element-admin':'web admin template','nwjs/nw.js':'runtime/framework','DioxusLabs/dioxus':'framework',
 'wailsapp/wails':'framework','quasarframework/quasar':'framework','zulip/zulip':'server/web app','matplotlib/matplotlib':'python library','dotnet/maui':'framework',
 'typicode/lowdb':'library','eclipse-theia/theia':'IDE framework','longbridge/gpui-kit':'ui library','JetBrains/compose-multiplatform':'framework','flet-dev/flet':'framework',
 'electron-userland/electron-builder':'build tool','PySimpleGUI/PySimpleGUI':'library','Manisso/fsociety':'script pack','CursorTouch/Windows-MCP':'MCP server',
 'kusti8/proton-native':'framework','rustdesk/rustdesk-server':'server','WebKit/WebKit':'browser engine','connors/photon':'framework/boilerplate',
 'vinceliuice/WhiteSur-gtk-theme':'theme','nodegui/nodegui':'library','microsoft/microsoft-ui-xaml':'ui framework','zhiyiYo/PyQt-Fluent-Widgets':'ui library',
 'revery-ui/revery':'framework','hrvach/deskhop':'hardware firmware','weolar/miniblink49':'browser kernel','ElectronNET/Electron.NET':'framework','electron/forge':'build tool',
 'os-js/OS.js':'web platform','nextapps-de/winbox':'js library','mviereck/x11docker':'script/tool','sshahine/JFoenix':'library','nodegui/react-nodegui':'library',
 'r0x0r/pywebview':'library','fschutt/azul':'framework','mimecorg/vuido':'library','serialport/node-serialport':'library','go-flutter-desktop/go-flutter':'framework',
 'nodegit/nodegit':'library','alex8088/electron-vite':'build tool','benoitvallon/react-native-nw-react-calculator':'demo','sindresorhus/electron-store':'library',
 'Kinnara/ModernWpf':'ui library','dotnet/winforms':'framework','microsoft/WindowsAppSDK':'sdk','MetaCubeX/metacubexd':'web dashboard','zhuzichu520/FluentUI':'ui library',
 'flutter-webrtc/flutter-webrtc':'plugin','ilyamiro/serpantinum':'shell config','milind-soni/OpenMausBot':'bot','elie222/rakazo':'bot',
}
extra = L('curation_extra_deny.json') if (D/'curation_extra_deny.json').exists() else {}
DENY.update(extra)
kept = [r for r in sel if r['repo'] not in DENY]
need = 300-len(kept)
pool = {r['repo']:r for r in json.load(open(D/'repos_all_candidates.json',encoding='utf-8'))} if (D/'repos_all_candidates.json').exists() else {}
cand = [pool[n] for n in ex['overflow'] if n in pool and n not in DENY]
refill = cand[:need]
final = kept+refill
json.dump(final, open(D/'repos.json','w',encoding='utf-8'), indent=1, ensure_ascii=False)
json.dump({'denied':{k:v for k,v in DENY.items()}, 'refilled':[r['repo'] for r in refill], 'final':len(final)}, open(D/'curation.json','w',encoding='utf-8'), indent=1)
print('kept',len(kept),'refill',len(refill),'final',len(final))
for r in refill: print(r['repo'],'|',(r['desc'] or '')[:50].encode('ascii','replace').decode())
