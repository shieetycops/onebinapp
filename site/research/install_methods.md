# Riset cara pasang per tool (diakses 2026-11-12, dari dokumentasi resmi)
Sumber: laporan researcher (model output). Hanya yang punya URL resmi di sini yang boleh jadi tombol. "tidak terdokumentasi" = tidak ada di sumber resmi yang terbaca; BUKAN berarti tidak ada. Catatan: halaman Claude Code MCP terpotong (100.000 dari 157.062 karakter), sehingga "tidak terdokumentasi" untuk Claude Code berarti tidak ada di bagian yang terbaca.

## Claude Code
- MCP CLI [https://code.claude.com/docs/en/mcp]: `claude mcp add --transport http <name> <url>`; `claude mcp add [options] <name> -- <command> [args...]` (`-e KEY=VAL`, `--transport stdio`); `claude mcp add-json <name> '<json>'`; `claude mcp list|get|remove`. Scope `-s local|project|user` (default local). Config: project `.mcp.json`; local/user `~/.claude.json`. Path per OS: tidak terdokumentasi (hanya `~`).
  - stdio: `{"mcpServers":{"name":{"command":"npx","args":["-y","pkg"],"env":{"K":"V"}}}}`; http: `{"mcpServers":{"name":{"type":"http","url":"https://example.com/mcp"}}}`
  - `.mcp.json` project butuh persetujuan di sesi interaktif. Deeplink MCP: tidak terdokumentasi.
- Skill [https://code.claude.com/docs/en/skills]: folder `~/.claude/skills/<name>/SKILL.md` (pribadi) atau `.claude/skills/<name>/SKILL.md` (project). Tidak ada perintah install (salin folder). Folder skill baru butuh `/reload-skills`.
- Plugin [https://code.claude.com/docs/en/plugins/install , https://code.claude.com/docs/en/plugins/create-marketplace]: `claude plugin marketplace add <owner/repo|path>` lalu `claude plugin install <name>@<marketplace> --scope user|project|local`; atau dalam sesi `/plugin marketplace add owner/repo`, `/plugin install name@marketplace`. Manifest `.claude-plugin/plugin.json`, katalog `.claude-plugin/marketplace.json`. Plugin bisa menjalankan hook dan MCP server dengan hak pengguna. Deeplink: tidak terdokumentasi.

## Claude Desktop
- MCP lokal [https://modelcontextprotocol.io/docs/develop/connect-local-servers]: file `claude_desktop_config.json`; macOS `~/Library/Application Support/Claude/`, Windows `%APPDATA%\Claude\`, Linux `~/.config/Claude/`. UI: Settings > Developer > Edit Config. stdio: `{"mcpServers":{"x":{"command":"npx","args":["-y","pkg"]}}}` (Windows: backslash di-escape). Restart penuh diperlukan. CLI: tidak terdokumentasi. HTTP di file config: tidak terdokumentasi.
- MCP remote [https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp]: UI Customize > Connectors > + Add > Add custom connector (berjalan dari cloud Anthropic).
- `.mcpb`: pasang lewat UI, bukan klik ganda [https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop]. Deeplink: tidak terdokumentasi.
- Skill [https://support.claude.com/en/articles/12512180-using-skills-in-claude]: unggah ZIP lewat Customize > Skills > + Create skill > Upload a skill. Direktori skill & perintah: tidak terdokumentasi.
- Plugin: hanya di tab Code Desktop, "+" > Add plugins [https://code.claude.com/docs/en/plugins/install].

## Cursor
- MCP [https://cursor.com/docs/context/mcp]: `.cursor/mcp.json` (project), `~/.cursor/mcp.json` (global); path per OS tidak terdokumentasi. stdio `{"mcpServers":{"n":{"command":"python","args":["mcp-server.py"],"env":{"API_KEY":"${env:API_KEY}"}}}}`; remote `{"mcpServers":{"n":{"url":"https://api.example.com/mcp","headers":{...}}}}`. Cursor meminta persetujuan sebelum memakai tool MCP. CLI MCP: tidak terdokumentasi.
- Deeplink [https://cursor.com/docs/context/mcp/install-links]: `cursor://anysphere.cursor-deeplink/mcp/install?name=$NAME&config=$BASE64_ENCODED_CONFIG` (config = JSON.stringify lalu base64). Contoh resmi hanya stdio `npx`; contoh remote tidak ada.
- Skill [https://cursor.com/docs/skills]: `.cursor/skills/`, `.agents/skills/` (project); `~/.cursor/skills/`, `~/.agents/skills/` (user); juga membaca `.claude/skills/`, `.codex/skills/`. Folder berisi SKILL.md; `name` = nama folder. Perintah install: tidak terdokumentasi.
- Plugin [https://cursor.com/docs/plugins]: UI Customize > cari > Install; CLI tidak terdokumentasi.

## VS Code
- MCP CLI [https://code.visualstudio.com/docs/copilot/reference/mcp-configuration]: `code --add-mcp '{"name":"playwright","type":"stdio","command":"npx","args":["-y","@playwright/mcp@latest"]}'` (menambah ke user profile mcp.json). Workspace `.vscode/mcp.json` [https://code.visualstudio.com/docs/copilot/customization/mcp-servers]; root key `servers`; stdio `{"servers":{"n":{"type":"stdio","command":"npx","args":[...]}}}`; http `{"servers":{"n":{"type":"http","url":"...","headers":{...}}}}`. Path user mcp.json per OS: tidak terdokumentasi. Deeplink MCP: tidak terdokumentasi. Server trust prompt muncul [https://code.visualstudio.com/docs/agents/run/manage-mcp-servers].
- Skill [https://code.visualstudio.com/docs/copilot/customization/agent-skills]: `.github/skills/`, `.claude/skills/`, `.agents/skills/` (project); `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/` (pribadi). Perintah install CLI: tidak terdokumentasi.
- Ekstensi [https://code.visualstudio.com/docs/editor/extension-marketplace]: `code --install-extension <publisher.extension>`.
- Agent plugins [https://code.visualstudio.com/docs/copilot/customization/agent-plugins]: Chat: Install Plugin from Source; deeplink `vscode://chat-plugin/install?source=<url-encoded>&plugin=<url-encoded-name>`; selalu minta konfirmasi; butuh `chat.plugins.enabled` (Experimental).

## OpenAI Codex
- MCP CLI [https://learn.chatgpt.com/docs/extend/mcp?surface=cli]: `codex mcp add <name> --env K=V -- <command>`; contoh `codex mcp add context7 -- npx -y @upstash/context7-mcp`; HTTP `codex mcp add example --url https://mcp.example.com` [?surface=ide]; `codex mcp list|login`. Config `~/.codex/config.toml` (project `.codex/config.toml` hanya untuk project trusted); path per OS tidak terdokumentasi. TOML stdio: `[mcp_servers.context7]` `command="npx"` `args=["-y","@upstash/context7-mcp"]`; HTTP `[mcp_servers.figma]` `url="..."` `bearer_token_env_var="..."`. Restart Codex setelah ubah config. Deeplink: tidak terdokumentasi.
- Skill [https://learn.chatgpt.com/docs/build-skills]: `.agents/skills` (repo), `$HOME/.agents/skills` (user). `$skill-installer <name>` hanya untuk skill terkurasi; `codex skills install` tidak terdokumentasi.
- Plugin [https://learn.chatgpt.com/docs/plugins]: `codex plugin marketplace add owner/repo [--ref main] [--sparse .agents/plugins]` lalu `/plugins`. "The IDE extension doesn't support plugins."

## Matriks yang BOLEH jadi tombol (aturan builder)
| Tool | MCP | Skill | Plugin |
|---|---|---|---|
| Claude Code | satu baris `claude mcp add` | manual: salin folder ke `~/.claude/skills/<name>/` | satu baris `claude plugin marketplace add` + `claude plugin install` (hanya bila repo punya `.claude-plugin/marketplace.json`) |
| Claude Desktop | potongan config + path per OS (stdio); remote: langkah UI | manual: ZIP + langkah UI | tidak ada tombol (hanya tab Code UI) |
| Cursor | sekali klik deeplink (HANYA stdio `npx`, sesuai contoh resmi); selain itu potongan `.cursor/mcp.json` | manual: salin ke `~/.cursor/skills/<name>/` | tidak ada tombol |
| VS Code | satu baris `code --add-mcp '<json>'`; atau potongan `.vscode/mcp.json` | manual: salin ke `~/.copilot/skills/<name>/` | deeplink `vscode://chat-plugin/install` (butuh setting eksperimental, ditulis di prasyarat) |
| Codex | satu baris `codex mcp add`; atau potongan config.toml | manual: salin ke `$HOME/.agents/skills/<name>/` | satu baris `codex plugin marketplace add` (hanya bila marketplace ada; bukan untuk ekstensi IDE) |
Sel di luar daftar = tidak ada tombol, tampilkan "belum ada cara pasang terdokumentasi untuk tool ini".
