"""Categories by GitHub topics only (SPEC section 3). Priority = order of CATEGORY_IDS; first category with a matching topic wins.
Framework/generic topics (electron, tauri, qt, gtk, desktop-app, flutter, cross-platform...) never map.
No topic mapped -> 'alat' and the app is counted in stats.uncategorized (categorize() returns mapped=False)."""
CATEGORY_IDS = ['media', 'produktivitas', 'ai', 'privasi', 'jaringan', 'sosial', 'baca', 'alat', 'game', 'developer']


def _s(x): return frozenset(x.split())


TOPICS = {
    'media': _s('music music-player audio audio-player player media media-player video video-player video-editor video-editing video-downloader youtube youtube-downloader downloader streaming podcast podcasts photo photos photography image image-viewer image-editor image-editing image-processing screen-recorder screen-recording screencast recorder obs live-streaming streamer jellyfin jellyfin-client emby-client pixiv gallery image-compression tinypng webp svg subtitles anime movies tv iptv radio spotify lyrics equalizer dj transcoder converter video-converter ffmpeg vlc mpv 3d animation drawing paint painting art design graphic-design vector gif camera webcam'),
    'produktivitas': _s('productivity notes note-taking note-app notetaking notebook markdown markdown-editor editor text-editor todo todo-app task-manager tasks calendar planner pomodoro timer time-tracking time-tracker office document documents pdf pdf-viewer pdf-editor spreadsheet excel knowledge-base second-brain obsidian wiki journal diary mind-map mindmap kanban project-management clipboard clipboard-manager launcher spotlight snippets whiteboard presentation latex writing writer email mail email-client mail-client rss-reader'),
    'ai': _s('ai artificial-intelligence llm llms chatgpt gpt openai claude anthropic gemini ollama chatbot chat-ui machine-learning ml deep-learning stable-diffusion generative-ai genai copilot ai-assistant assistant agent agents langchain rag claude-code codex ai-agents ai-agent coding-agent multi-agent agent-orchestration multimodal computer-vision speech-to-text text-to-speech whisper tts stt ocr transcription mcp'),
    'privasi': _s('privacy security password password-manager passwords encryption encrypted cryptography keepass bitwarden 2fa totp authenticator vpn tor anonymity anonymous secure secrets gpg pgp firewall adblock ad-blocker ad-block anti-tracking tracking-protection'),
    'jaringan': _s('network networking vpn proxy proxy-client clash v2ray shadowsocks trojan wireguard ssh sftp ftp ftp-client sftp-client remote-desktop remote-access rdp vnc torrent bittorrent torrent-client download-manager p2p file-transfer file-sharing wifi dns browser web-browser chromium sing-box xray socks5 tunnel'),
    'sosial': _s('chat messenger messaging instant-messaging social social-media discord telegram whatsapp slack matrix mastodon twitter bluesky signal irc xmpp video-call video-conferencing voip fediverse reddit wechat qq weibo bilibili douyin tiktok livestream'),
    'baca': _s('ebook ebooks e-book epub reader ebook-reader book books comics comic comics-reader manga manga-reader comic-reader library-manager calibre news news-reader feed-reader reading read-it-later bible dictionary translation translator language-learning flashcards anki'),
    'alat': _s('utility utilities tool tools file-manager file-explorer explorer system-monitor system-tools system-utility monitor monitoring disk cleaner backup google-drive onedrive file-search sync synchronization screenshot screenshots screen-capture ocr-tool wallpaper wallpapers customization tweaks windows-tweaks theme-manager launcher-tool renamer file-renamer batch rename archive archiver zip compress compression unarchiver uninstaller installer package-manager hardware benchmark battery bluetooth keyboard mouse macro automation autohotkey hotkey widget widgets menubar menu-bar taskbar statusbar tray status-bar dock'),
    'game': _s('game games gaming game-launcher gamedev emulator emulators retro retro-gaming steam minecraft minecraft-launcher chess puzzle roguelike rpg fps game-engine game-development gamepad controller nintendo playstation xbox gba nes snes psp ps2 ps3 n64 mame'),
    'developer': _s('cli devtools dev-tools developer-tools developer-tool development git git-client github gitlab ide code-editor terminal terminal-emulator shell api-client rest-client http-client graphql postman database database-client sql sqlite postgresql mysql mongodb redis docker kubernetes devops debugger debugging profiler log-viewer json yaml regex programming vscode vim neovim jetbrains hex-editor hex api testing'),
}
# topics too generic to decide anything
IGNORED = _s('electron tauri qt gtk gtk3 gtk4 desktop desktop-app desktop-application flutter flutter-desktop cross-platform crossplatform windows linux macos mac osx android app application open-source opensource gui rust python javascript typescript react vue svelte nodejs c cpp csharp dotnet java kotlin swift go golang nextjs wails neutralino electron-app')


def categorize(topics):
    """-> (category_id, mapped: bool)."""
    ts = {t.lower() for t in topics or []} - IGNORED
    for cid in CATEGORY_IDS:
        if ts & TOPICS[cid]:
            return cid, True
    return 'alat', False
