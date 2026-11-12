# Round 3: closing status (2026-11-11), on the user's instruction "stop evaluating, close as-is"
LOCK.md is unchanged since the re-lock (hash in hashes.txt). Evaluation was NOT finished; nothing below is a pass/fail verdict for the product decision.

## Done
- Smoke test chunk 00 passed; rule change recorded in LOCK.md section 0a; hashes re-locked before the draw.
- Draw: stopped by rule at 300 repos (246 curated, 509 strict-extension assets; 100 per source). Labeling: both labelers, 2 chunks, all rows present.
- Header probe: 509/509 HTTP 206.
- Gate before the sample (data/round3/gate_round3.json, scripts/19_gate_round3.py), verified precision / coverage / unverified share:
  windows x64 100% (n=43, Wilson lo 91.8%) / 38.4% / 41%; macos arm64 100% (65) / 55.6% / 34%; macos x64 100% (51) / 49.0% / 40%; linux x64 100% (57) / 90.5% / 0%.
  Old strict precision (secondary): 58.9 / 65.7 / 60.0 / 100.
  By the LOCK targets: linux passes; windows and macOS miss COVERAGE (>=90%), not precision.

## Not done
- dmg/pkg 30-file sample (LOCK 0a): NO valid result. Run 1 reported 30/30 "tidak bisa dibuka" because of a wrong 7-Zip extraction pattern (my bug; 7-Zip 21.04 does open these dmg). That file is kept as dmg_pkg_sample_result.INVALID_extraction_bug.json and must not be used. The fixed script (scripts/20_dmg_pkg_sample.py) was killed by the system for low memory; not rerun. So the macOS sample check is OPEN and macOS has no verdict under 0a.
- Reported per LOCK as not finished: per-source gates, final decision mapping (section 8).
## Caveats
- scripts/19 and 20 were written after the lock (not in the locked list); hashes in draw_hashes.txt.
- Gold for role/type/arch-by-name is two-model agreement, not human confirmation.
## Known bug in scripts/19_gate_round3.py (reported, not fixed; LOCK: no fixes after the draw)
Coverage denominator adds a repo when ANY strict candidate is unverified and none is correct; LOCK section 7 says ALL candidates must be unverifiable. A repo with one verified-wrong helper plus one unknown-arch exe is counted, so windows/macOS coverage may be understated. Not recomputed. picker_v3 is NOT to be tuned (that would be a fourth round, needs the user's approval).
