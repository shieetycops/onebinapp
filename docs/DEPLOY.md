# Deploy: Cloudflare Pages + daily update

Nothing has been pushed or deployed. The workflow files are in `.github/workflows/` (`daily.yml`, `ci.yml`) and have never run on GitHub.

## What you do yourself (short list)

1. **Create an empty GitHub repo** (public or private) and push `main`:
   `git remote add origin https://github.com/<you>/<repo>.git` then `git push -u origin main`.
2. **Create a GitHub token for the build** (Settings > Developer settings > Fine-grained tokens): resource owner = you, repository access = "Public repositories (read-only)", no extra permissions. Expiry: the longest you accept; put the renewal date in your calendar.
3. **Add repo secrets** (repo > Settings > Secrets and variables > Actions):
   - `CATALOG_GH_TOKEN` = the token from step 2 (the built-in `GITHUB_TOKEN` is limited to 1,000 requests per hour per repository, too small for this build).
   - `CLOUDFLARE_API_TOKEN` = an API token with permission "Cloudflare Pages: Edit".
   - `CLOUDFLARE_ACCOUNT_ID` = your account id (Cloudflare dashboard, right sidebar).
4. **Create the Pages project as "Direct Upload"** (Cloudflare dashboard > Workers & Pages > Create > Pages > Upload assets) with any name, e.g. `jembatan-rilis`. Do NOT connect it to the Git repo: Pages cannot run the Python and history pipeline.
5. **Add repo variable** `CF_PAGES_PROJECT` = that project name (Settings > Secrets and variables > Actions > Variables).
6. **Allow the bot commit**: Settings > Actions > General > Workflow permissions = "Read and write". (If `main` is protected, allow the Actions bot to push, or the state commit fails.)
7. **Run it once**: Actions > daily-catalog > Run workflow. The first run has cold caches (full registry crawl about 70 minutes, star lookups, a REST pass for every repo) and **may hit the 170-minute limit**. If it does, just start it again: the caches saved by the failed run (each run saves under its own key) carry the progress forward. After that it runs by itself every day at 03:17 UTC and the registry is read incrementally (about 75 seconds instead of 70 minutes; a full crawl once a week).

Trending stays hidden for about a week: it needs a star snapshot 6 to 9 days old (30-day trends need one 27 to 33 days old).

## What the daily run does

1. Restores the raw caches (metadata, ETags, release lists, registry crawl). If they were evicted, the run is only slower.
2. Clones komi-store-backend-data fresh (a candidate source) and checks the sha256 of the locked picker/classifier.
3. `discover.py`: looks for new desktop-app repos in the same sources as round 3 (komi, Homebrew cask list, GitHub topics electron / tauri / desktop-app / qt / gtk / flutter-desktop). At most 150 new names per day, appended to `data/discovered.txt`. They go through the SAME curation as every other repo.
4. `build_catalog.py`: repo metadata by light GraphQL (cost about 1 point per 25 repos). Releases by REST with `If-None-Match` (a 304 means "unchanged", the cached copy is reused, and in a test of 14 repos the 304 answers were not counted by GitHub's rate limit). Repos already rejected by the metadata curation or the deny list get no release request at all. The share of 304 answers is printed and stored in `stats.json` under `releases_rest`; it is not assumed. Download counts live inside the release data, so popular repos often return 200.
5. `build_ai.py` (registry + topic crawl), `usage_fetch.py`, then the AI catalog is rebuilt from cache so the "Cara pakai" data is included.
6. Python tests, then `npm run build` (static export to `site/out`).
7. Commits `data/history/` (star snapshots), `data/changelog/` and `data/discovered.txt` back to `main` (one small commit per day; cache eviction must never reset trending).
8. `wrangler pages deploy site/out`.

## When a repo cannot be fetched

The repo keeps its previous cached data for up to 7 days (`--max-stale-days`) and the build continues. Counts are in `stats.json` / `stats-ai.json` under `freshness` (`stale_reused`, `stale_expired`, `missing`, and the 25 oldest stale repos). After 7 days the repo is dropped and the changelog says `stale_expired`.

**Guard:** if more than 20% of the repos are not fresh (`--max-not-fresh 0.2`), the builder exits with code 4 before writing anything. The job fails, nothing is committed or deployed, and yesterday's site stays up. The footer date therefore only moves when a build really succeeded.

## Budget and growth (read this)

Download counts are inside the release data, so on a daily cadence most popular repos return 200, not 304; ETag saves little for them. Plan on about one counted REST request per catalog repo per day (about 2,100 today, limit 5,000 per hour for the personal token). `discover.py` adds up to 150 candidates a day; the ones that fail the metadata curation cost nothing in REST calls, but the ones that pass add to the catalog and to the daily request count. If the catalog keeps growing, lower `--max-new` or the run will start sleeping on rate-limit resets.

## Changelog

`data/changelog/desktop.jsonl` and `ai.jsonl`: one line per day with `added` (repo, stars, source) and `removed` (repo, reason). Reasons are the curation codes (`C1`..`C4b`, `R1`..`R8`), `no_release`, `no_installer`, `manual_deny`, `not_found`, `stale_expired`, `fetch_failed`, or `rank_cutoff` (AI: fell out of the top 200). The first day is a baseline. The last 60 days are published as `/data/changelog.json` and `/data/changelog-ai.json`. A second run on the same day replaces that day's line and still diffs against the start of the day.

## Limits checked (verify again before relying on them)

- Cloudflare Pages: 20,000 files per site on the Free plan, 25 MiB per file. Check `site/out` after a build (`find site/out -type f | wc -l`).
- GitHub Actions caches: 10 GB per repo, evicted after 7 days without access.
- `GITHUB_TOKEN`: 1,000 requests/hour/repository; personal token: 5,000/hour.

## Running the same thing locally

```
python -I scripts/catalog/discover.py
python -I scripts/catalog/build_catalog.py
python -I scripts/catalog/build_ai.py
python -I scripts/catalog/usage_fetch.py && python -I scripts/catalog/build_ai.py --offline --no-changelog
cd site && npm run build
```
Do not run these at the same time as `next build` or Playwright (memory). Token: `GH_TOKEN` or `~/.gh_token`; it is never written to any output.
