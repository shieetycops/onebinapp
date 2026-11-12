# Definisi tetap (ditulis sebelum menghitung cakupan & sebelum melihat data winget/Cask)
Tier STRICT "siap klik": Windows .exe(installer: nama mengandung setup/install, atau .exe tak-ambigu) / .msi / .msix / .appx ; macOS .dmg / .pkg ; Linux .AppImage
Tier LOOSE = STRICT + Windows portable/ambiguous .exe & zip ; macOS .app.zip/zip ; Linux .deb/.rpm/.flatpak/.snap
.exe tanpa petunjuk di nama = "ambiguous" (dihitung di LOOSE saja; dilaporkan sebagai batas atas ketidakpastian).
Arch dilaporkan terpisah: macOS arm64/x64/universal, Windows x64/arm64.
Picker (urutan preferensi, ditetapkan sebelum membuka winget/Cask):
 windows: exe-installer > msi > msix/appx > exe-ambiguous > portable zip
 macos  : dmg > pkg > zip
 linux  : AppImage > deb > rpm > flatpak > snap > tar/zip
 arch   : cocok persis > universal/any > unknown ; tidak pernah memilih arch yang salah.
