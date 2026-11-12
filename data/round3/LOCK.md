# Round 3: lock file (written 2026-11-11, BEFORE any repo of the third sample was searched, fetched or labeled)

The old gate ("OS >= 95% on all assets") is recorded as FAILED in report/index.html and stays there. This round measures what the product does.
After the draw nothing in this file changes. A bug found later is reported, not fixed. No fourth round without the user's approval.

## 0. Status
Earlier (superseded): BLOCKED before the draw because the edited labeler-a / labeler-b definitions were not loaded (smoke test chunk 00 wrote no file). The user ruled out prompt overrides and substitute agent types.
2026-11-11, after session restart: smoke test chunk 00 PASSED. data/labeler3/out_a/labels_00.csv and out_b/labels_00.csv exist at the fixed paths with header `id,OS,arch,type,role,conf_os,conf_arch,conf_type` and 3 rows each (verified from the files). Hashes of the files listed in section 1 were checked with `sha256sum -c` before the edit below and all matched. The draw has NOT started.

## 0a. Change before the draw (2026-11-11, on the user's instruction; applies to sections 6 and 7)
OLD rule: an asset whose gold arch is "unknown" (not in the name, not readable from content) is unverifiable = NOT correct in the strict number; the precision denominator is all offered buttons.
NEW rule: an architecture missing from the name does not make an asset wrong automatically. Reason (user): the old rule counted "no token" as an error, which measures name hygiene, not whether the download runs on the machine.
Everything else in this file stays. In particular: the picker reads names only (header reads feed gold only); the PE 32-bit rule stays (a 32-bit PE says nothing about the installer target, so it is "tidak terverifikasi", never a guessed x86/x64); coverage keeps its section 7 definition; role/type gold basis is unchanged.

Arch resolution for an asset whose name has no arch token (an asset with a token keeps name + labeler agreement as in section 6):
- .exe, .msi, .AppImage: arch from the file header via Range request (scripts/13_probe_headers.py, EVAL_DIR=data/round3, first 512 KiB; MSI 4 MiB), then judged with the same runs-on table (section 5).
- .dmg, .pkg: see "dmg/pkg sample" below. Outside the sample they are not opened.
- All remaining no-token assets (every .dmg/.pkg not read, .msix/.appx, anything the probe cannot read) go to the group "tidak terverifikasi".

dmg/pkg sample (fixed now):
- Population: distinct (repo, asset_name) of .dmg and .pkg assets that the picker OFFERS in at least one gated macOS cell on /releases/latest, whose name has no arch token. If the population has fewer than 30, take all and report n.
- Method: sort by "repo|asset_name", then random.Random(20261120).sample(list, 30). The seed is fixed here; no resampling.
- Each sampled file is downloaded in full to the scratchpad, one new empty directory per file, parsed with `python -I`, never executed. Tool: 7-Zip 21.04 (C:\WINDOWS\system32\7z.exe) to list/extract; arch = Mach-O header of the main executable under *.app/Contents/MacOS/ (fat header with arm64 and x86_64 = universal; fat header with one arch = that arch); for .pkg, xar `hostArchitectures` or Mach-O payload if the xar has none. If a file cannot be opened on this machine (e.g. APFS-only dmg that 7-Zip 21.04 cannot read), it is recorded "tidak bisa dibuka" per file, reported, and NOT guessed. It counts neither as wrong nor as right, and is listed in the sample report.
- A sampled file is WRONG if its arch is not in the runs-on set of a gated macOS cell it was offered in (e.g. arm64-only offered to macos x64 is wrong; x64-only offered to arm64 is fine via Rosetta). Failing any gated cell it was offered in = wrong.
- Sample error rate = wrong / (files opened and read). Unopened files are excluded from the denominator and reported separately. If this rate is above 2%, macOS is declared FAILED even if its verified numbers pass. With n=30 a single wrong file is 3.3% (> 2%), so in practice this check is zero-tolerance; with fewer than 30 opened, the same arithmetic applies to the realized n.
- A no-token .pkg whose arch the Range probe reads (xar hostArchitectures, section 6) is "verified" for precision AND stays in the sample population; the sample draw is not affected by it.

Gate and reporting under the new rule:
- Verified offered = offered buttons whose arch gold is determined (name token, header, or labeler agreement as in section 6) and whose OS/role/type gold is resolved. Unverified offered = offered buttons with no-token arch that stayed in "tidak terverifikasi" or whose header was unreadable, plus UNRESOLVED labeler cases as in section 7.
- Gate precision (>= 98%) = verified offered buttons with gold CORRECT / verified offered buttons. n offered >= 30 rule applies to verified offered.
- Reported separately, never gating on their own: (a) percentage of unverified offered per OS (and per gated cell); (b) error rate of the 30-file dmg/pkg sample (above); (c) the OLD strict precision (no token / unknown = wrong; denominator all offered) as secondary figure.
- Coverage, strictest-number rule, n small rule, decision mapping (section 8): unchanged, except that the macOS sample check above is an additional fail condition for macOS.

## 1. Hashes (data/round3/hashes.txt, sha256, taken when this file was written)
scripts/classifier_v3.py, scripts/picker_v3.py (contains the COMPAT table and gated cells), scripts/test_v3.py, data/labeler3/input/labels_guide.txt, .claude/agents/labeler-a.md, .claude/agents/labeler-b.md, data/round3/seen_repos.txt, this LOCK.md. classifier.py and classifier_v2.py are untouched (hashes in data/classifier_hashes.txt).
The picker reads NAMES only. It never reads file headers (otherwise content-gold rows would equal its input).

## 2. Sources and proportions (pool is interleaved 1:1:1 from three shuffled lists)
- komi: unique `fullName` in komi-store-backend-data/cached-data (commit e11dbea...), minus seen.
- cask: GitHub repos named in `url` or `homepage` of data/ext/cask.json, minus seen. Known bias: every cask repo ships a macOS build.
- gh_search: GitHub Search API, `topic:T stars:100..999 fork:false archived:false`, T in {electron, tauri, desktop-app, qt, gtk, flutter-desktop}, sort=stars order=desc, pages 1-10 x 100. Raw responses saved under data/round3/search_raw/ (results drift). Minus seen.
- Seen exclusion: data/round3/seen_repos.txt (1148 repos: the original 300, the curation candidates and denied/refilled lists, the 250 of the clean round). Case-insensitive.
- Each source list is shuffled with random.Random(20261114 + source index: komi 0, cask 1, gh_search 2) after sorting names; a repo present in several sources is kept in the first source in the order komi, cask, gh_search. Realized proportions per source are reported.

## 3. Curation (name, description, topics, stars and flags ONLY; deterministic; one recorded decision per repo in data/round3/curation_decisions.json)
Metadata: GET /repos/{r} (raw saved). A repo is "curated" if all hold:
- C1 not fork, not archived, not disabled.
- C2 stargazers_count >= 100.
- C3 description non-empty.
- C4a no whole-token (case-insensitive) match in name, description or topics of: library, lib, framework, sdk, boilerplate, template, starter, plugin, extension, theme, icons, dotfiles, awesome, tutorial, example, demo, driver, firmware, kernel, compiler, linter, backend.
- C4b "CLI or dev tool" rule: if topics contain `cli` or `command-line` and contain none of {desktop-app, electron, tauri, gui, qt, gtk, desktop, flutter-desktop}, the repo is excluded. A CLI that ships an .msi without GUI topics is therefore out of scope (the product is for laypeople).
Asset candidate ("tombol download") = asset of /releases/latest with a strict extension: windows .exe .msi .msix .appx(+bundle); macos .dmg .pkg; linux .AppImage. Nothing else (no zip, deb, rpm, snap, flatpak).
A curated repo "qualifies for OS X" if it has at least 1 asset with a strict extension for X (extension only; before any helper filter, before the picker).

## 4. Stopping rule and cap
Process the pool in order in fixed batches of 100 repos (metadata, curation, latest release, extension check). Stop after the first batch at the end of which every OS has >= 60 qualifying curated repos. Hard cap: 1200 repos fetched. If the cap is hit first, report n as reached; an OS with < 60 qualifying repos is flagged "n kecil" and cannot pass. Stopping depends only on extension counts, never on picker output or gold labels.

## 5. Cells and the compatibility table (machine = cell; what runs there)
Gated cells: windows x64; macos arm64; macos x64; linux x64. (Other cells: reported only.) The OS gate for macOS passes only if BOTH mac cells pass.
runs-on table: windows x64 {x64, x86, universal/any}; windows arm64 {arm64, x64, x86, universal/any}; macos arm64 {arm64, universal/any, x64 (Rosetta)}; macos x64 {x64, universal/any}; linux x64 {x64}; linux arm64 {arm64}.
The picker itself never offers cross-arch (silence rules S1-S5 in picker_v3.py header).

## 6. Gold ("benar") and its basis
Rows to label: EVERY asset with a strict extension in every curated repo (including those the picker would filter as helper or ambiguous exe).
An asset is CORRECT for a cell iff all hold: gold OS = cell OS; gold role = app (not helper, updater, uninstaller, redistributable, CLI, debug, legacy); for .exe gold type = installer; gold arch is known and in the runs-on set of the cell (gold arch "unknown" = unverifiable = NOT correct in the strict number).
Gold basis per field, in this order:
- OS: file content if readable (exe/msi PE or OLE = windows; AppImage ELF = linux; pkg xar = macos), else labeler agreement.
- arch: content only for PE64/arm64, MSI Template, ELF (AppImage), pkg xar hostArchitectures (the PE 32-bit rule stays: a 32-bit PE says nothing about the installer target), else labeler agreement. dmg and msix: names only, labeler agreement (Cask `variations` is NOT used).
- role, type: labeler agreement only, tag "kesepakatan agent, tanpa pemeriksaan manusia".
Labeler agreement = labeler-a and labeler-b give the same value and neither marked that column `ragu` (per-column confidence). Otherwise UNRESOLVED, counted as NOT correct in the strict number.
Range probe: scripts/13_probe_headers.py with EVAL_DIR=data/round3 (first 512 KiB; MSI 4 MiB).

## 7. Gate definitions (per cell, per OS; targets: precision >= 98%, coverage >= 90%)
- OFFERED = picker output is not None for (cell, repo) on /releases/latest of every curated repo qualifying for the OS of the cell.
- Precision (strict) = offered buttons whose gold is CORRECT / offered buttons. Reported with the breakdown: verified wrong, unverifiable/unresolved (counted wrong). Also reported (secondary, never gate): OS-only precision (by construction ~100%, dry run on 540 dev releases: 0 wrong of 987), exact-arch precision (asset arch equals the cell arch or universal), Wilson 95% lower bound.
- Coverage (strict) = repos with an offered AND CORRECT button / (repos with >= 1 CORRECT candidate for the cell + repos whose strict-extension candidates are all unverifiable/unresolved and none is verified correct). The latter group is also reported separately. Offered-any coverage is reported as secondary.
- The strictest number of an OS = the minimum of its gated precision and coverage values over its gated cells. An OS passes iff that minimum meets its target AND n offered >= 30 AND qualifying repos >= 60. A class or cell with < 30 offered is "n kecil" and cannot pass alone.
- Gates per source (komi, cask, gh_search) are secondary.

## 8. Decision mapping (fixed now)
All three OS pass: decision becomes "lanjut ke prototipe 20 app". Otherwise: report which OS fail and by which number, and propose launching the OS that pass first. Old gate stays in the report as failed.

## 9. Labeler procedure
- labeler-a (opus) and labeler-b (sonnet), tools Read and Write, definitions in .claude/agents/. The prompt carries only a two-digit chunk number. Input data/labeler3/input/assets_NN.csv (id, asset_name) and labels_guide.txt; output data/labeler3/out_a/labels_NN.csv resp. out_b/labels_NN.csv. At most 400 rows per chunk, one call per labeler per chunk. Columns: id,OS,arch,type,role,conf_os,conf_arch,conf_type.
- Nobody copies or edits labeler output by hand. Scripts only parse the files.
- Gate before the draw: smoke test chunk 00 (3 rows) must produce files at the fixed paths with the new header. If the old definition is still in effect: stop and report that a session restart is needed. No prompt override, no substitute agent type.
- The claim that labelers read only the two permitted files stays unverified (instruction + tool-use count).

## 10. Known limits written down in advance
Cask source is macOS-biased and komi leans toward installers (shares reported). Labeler agreement of two models is not human confirmation. dmg and msix arch rest on names only. Bare-binary arch reader in classifier_v3 cannot move this gate (bare binaries are not strict candidates).
