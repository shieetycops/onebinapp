# Cara pakai per tool (verifikasi, copot, pengaturan): sumber untuk scripts/catalog/usage_methods.json
Dibaca 2026-11-12. Isi tiap sel ada di usage_methods.json beserta source_url. Label: "tidak terdokumentasi" = halaman resmi tidak memuatnya; "inferred" = langkah umum, bukan instruksi resmi (ditandai di situs).
Halaman yang dibaca: code.claude.com/docs/en/{mcp,skills,discover-plugins,desktop}; modelcontextprotocol.io/docs/develop/connect-local-servers; cursor.com/docs/{context/mcp,skills,plugins}; code.visualstudio.com/docs/{agents/run/manage-mcp-servers,copilot/reference/mcp-configuration,copilot/customization/agent-skills,copilot/customization/agent-plugins}; learn.chatgpt.com/docs/{extend/mcp,build-skills,plugins} (developers.openai.com/codex/* mengalihkan ke sini; domain OpenAI).
## Celah yang dicatat
- Claude Code skill: tidak ada perintah copot (inferred: hapus folder). Cursor skill/plugin dan VS Code skill: copot tidak terdokumentasi. Claude Desktop (aplikasi chat) skill: halaman support.claude.com tidak dibaca, sel kosong.
- Claude Desktop MCP copot stdio: tidak terdokumentasi (inferred: hapus entri config, restart).
- Codex: `codex mcp remove`, `codex plugin remove`, `codex plugin marketplace remove` ada di `--help` CLI terpasang tetapi tidak di halaman dokumentasi. Hapus skill hanya via [[skills.config]] enabled=false.
- Path file config per OS tidak terdokumentasi untuk Claude Code MCP, Cursor, VS Code.
- Perbedaan dengan install_methods.md: setting VS Code chat.plugins.enabled tidak berlabel Experimental di halaman plugin sekarang (situs masih menampilkan prasyarat itu); lokasi skill VS Code Copilot = .github/skills/ dan ~/.copilot/skills/.
