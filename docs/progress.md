# Progress and handoff

**Read this first in every new session.** It says where the project stands and what happens next. Details live in `docs/decisions.md` (D001–D015), `docs/model_card.md` and `docs/data_sources.md`. Update this file at the end of every working session.

_Last updated: 2026-11-19_

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0: Data reconnaissance | ✅ Accepted | SA boundaries wait on PIRSA |
| 1: Label archive | 🟡 Built; checkpoint open | 1 green scheduled `archive_status` run so far (19 Nov 02:18 UTC). Needs the next one (21:00 UTC). |
| 2: Feature dataset | ✅ Accepted (Tasmania) | SA features wait on PIRSA |
| 3: Model | ✅ Approved to ship | Calibrated chlorophyll persistence (D013); deployed as `persistence-1.1` after one recalibration (D014). The test was scored once at commit `d881905`; never re-tune on it. |
| 4: Daily forecast pipeline | 🟡 Working; checkpoint open | The 1st scheduled run failed (theLIST refused the runner), so area pixels moved to the `TAS_AREA_PIXELS` secret. Manual run green 19 Nov. Needs 2 consecutive green **scheduled** runs (22:17 UTC). |
| 5: Frontend | 🟡 Live, iterated with Timothy | https://koiiphish.github.io/AlgalBloom/. "Clean marine" style, Inter, positron basemap; summary panel + More info; resizable panel; report-style wording; disclaimer in footer and panels (D015). Checkpoint: the live URL, reported together with Phases 1 and 4. |
| 6: Portfolio polish | ⬜ Not started | Needs approval after the checkpoints |

## Next steps

1. **Claude:** check the scheduled runs on 20 Nov via the public API (`curl https://api.github.com/repos/koiiphish/AlgalBloom/actions/runs`, and `status.json` from the live site):
   - Is `archive_status` green?
   - Is `daily_forecast` green?
   - Did the archive commit land?
   - What was `inputs.chl_age_days`?
   - Did Pages rebuild?
2. After a second consecutive green `daily_forecast` (21 Nov), report the Phase 1, 4 and 5 checkpoints together.
3. **Phase 6 (after approval).** Candidates discussed:
   - README with screenshots and an architecture diagram;
   - a "How it's doing" verification page (satellite hit rates; closures and Biotoxin News once months of archive exist);
   - per-area links to the ShellMAP management-plan maps (26 of 29 growing areas match);
   - a site name or URL change if wanted;
   - tightening the model card's wording.
4. **Before 24 Nov:** back up `data/raw/copernicus/history_olci_300m_v202211` (1.9 GB), because that version retires.

## How to preview the site locally

```
uv run python -m pipeline.forecast.daily --site _site      # data (no --archive locally)
uv run python -m pipeline.publish.web --site _site         # web files (also run by daily)
uv run python -m http.server -d _site 8000
```

Screenshots: headless Edge driven over the DevTools protocol with a small Node script. One-shot `--screenshot` stalls MapLibre's worker.

## Waiting on others

- **PIRSA (SASQAP):** SA harvest-area boundaries, and permission for one automated status read per day. `pir.sa.gov.au` returns 403 to scripts.
- **theLIST:** licence for ShellMAP Harvest Area Boundaries (layer 92). Until it's confirmed, publish **points only, never polygons**.

## Known issues and dates

- **Tier thresholds are quoted on the About page** (19% / 36%). Update it if the model is recalibrated.
- **2026-11-24:** the OLCI MY version 202211 (training history) retires. The local copy is in `data/` and is worth backing up.
- **2027-01-12:** the OLCI NRT version 202207 (the daily input) retires. Re-check the offset against the 202611 version before switching (D014).
- ~~Inland lakes in the chlorophyll layer~~: fixed in Phase 5 (sea-connected mask).
- **Phase 4 commit message:** commit `7363f6c` also contains the deployment model file, the SST climatology and the archive seed, but its message doesn't say so.

## Where data is stored (no database needed)

- **Published files** are on the `gh-pages` branch, which GitHub Pages serves.
- **Forecast archive:** `archive/` (CSV) on `main`.
- **Label history:** `labels/` on `main`.
- **Model files:** `models/` on `main`.
- **Raw downloads:** `data/`, on the laptop only.

Revisit this only if the archive grows to tens of MB a year (then switch to Parquet) or user accounts are added. Decided 2026-11-18.

## Session habit

Start each session fresh rather than resuming the old one, and say "continue". End each session with "update progress.md".

## Standing reminders

- Run `git pull --rebase` before pushing, because bots commit to `main` daily.
- The repo is public, so treat every commit as published.
- uv lives at `/c/Users/timne/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe`. Add it to PATH in Git Bash.
- In Git Bash, heredocs with apostrophes fail. Write files with the editor tools instead.
