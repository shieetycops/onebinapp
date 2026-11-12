# Rebuilding the catalog

One command, idempotent, standard library only:

    python -I scripts/catalog/build_catalog.py

What it does
- Verifies sha256 of `scripts/picker_v3.py` and `scripts/classifier_v3.py` against `data/round3/hashes.txt` and refuses to run on mismatch (exit 2).
- Candidate repos = union of `data/round3/seen_repos.txt`, round-3 drawn repos, komi cached-data `fullName`s and `data/catalog_extra.txt` (one `owner/repo` per line, `#` comments allowed).
- Fetches GraphQL in batches (default 25, halves automatically on RESOURCE_LIMITS errors), prints the measured `rateLimit cost/remaining` per query, appends to `data/catalog_cache/cost_log.jsonl`.
- Raw per-repo responses go to `data/catalog_cache/repos/` (never published). Cache entries younger than `--max-age-hours` (default 20) are reused, so a crashed or rate-limited run resumes where it stopped.
- A repo that fails to fetch keeps its previous cache (stale, up to 7 days) instead of stopping the build; exit 4 when too many are not fresh.
- Writes (atomically) `site/public/data/catalog.json`, `apps/<slug>.json`, `stats.json`, `trending.json`, and `data/history/snapshot-YYYY-MM-DD.json` (overwritten on the same day).
- `--limit N` / `--only owner/repo` are test modes: outputs go to `data/catalog_test_out/`, no snapshot is written, nothing under `site/public/data/` is touched.
- `--fetch-only` fills the cache without building.
- Tests: `python -I scripts/catalog/test_catalog.py`.

Token: environment variable `GH_TOKEN` (or `GITHUB_TOKEN`), else `~/.gh_token`. It is never printed or written to any output.

Trending: `trending.json` has `ready=false` until a history snapshot 6-9 days old exists (d30 needs one 27-33 days old); then card `trending.d7/d30/rank` are filled. Ranking = repos with d7 > 0, top 50.

Do not run this at the same time as `next build` or Playwright (memory).

## Daily workflow

The real workflow is `.github/workflows/daily.yml` (see `docs/DEPLOY.md`). Exit codes of `build_catalog.py`: 0 complete, 2 refused (hash mismatch / no token), 4 guard (more than 20% of repos not fresh; nothing written), 3 only with `--strict`. Releases come from REST with ETag by default (`--releases graphql` restores the old heavy query); a repo that cannot be fetched keeps its previous data for `--max-stale-days` (7).

## Trending options (SPEC_TRENDING)

Both builders (`build_catalog.py`, `build_ai.py`) accept:
- `--history-dir DIR` where the star snapshots live (default `data/history`; `snapshot-*.json` for desktop, `ai-snapshot-*.json` for AI).
- `--with-github-trending`, OFF by default. When set: at most 2 HTTP requests to github.com/trending per build in total (daily, weekly; a retry spends from the same budget; a result younger than 6 hours is reused from `data/catalog_cache/github_trending.json`), identifying User-Agent, one retry, any failure is logged and the build continues without it. GitHub has no official API or written permission for this; that is why it is opt-in. The repo names are appended to `data/trending_candidates.txt` and curated like every other candidate (desktop: C1-C4b + installer; AI: R1-R8). Rejections are counted in `stats*.json` under `trending_candidates`.

Outputs: `trending.json` (desktop) and `trending-ai.json`. `ready` stays false until a snapshot 6-9 days old exists (d30 needs one 27-33 days old). Tests: `python -I scripts/catalog/test_trending.py`.
Regenerating from caches without fetching: `--max-age-hours 1000000` (desktop) and `--offline` (AI); pass `--history-dir` to a copy of `data/history` if you do not want a new snapshot recorded.
