# Progress and handoff

**Read this first in every new session.** It says where the project stands and what happens next. Details live in `docs/decisions.md` (D001–D018), `docs/model_card.md` and `docs/data_sources.md`. Update this file at the end of every working session.

_Last updated: 2026-11-24_

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0: Data reconnaissance | ✅ Accepted | SA boundaries wait on PIRSA |
| 1: Label archive | 🟢 Checkpoint met, awaiting sign-off | 7 green scheduled `archive_status` runs (18–24 Nov); 1 status change captured (Triabunna Zone B, Open → Closed, 23 Nov). |
| 2: Feature dataset | ✅ Accepted (Tasmania) | SA features wait on PIRSA |
| 3: Model | ✅ Approved to ship | Calibrated chlorophyll persistence (D013); deployed as `persistence-1.1` after one recalibration (D014). The test was scored once at commit `d881905`; never re-tune on it. |
| 4: Daily forecast pipeline | 🟢 Checkpoint met, awaiting sign-off | 5 consecutive green scheduled `daily_forecast` runs (20–24 Nov). Data age 2 days every day; no stale areas; archive commits landing; Pages rebuilding. Runs start 2–8 h after the 22:17 UTC schedule (GitHub queue). |
| 5: Frontend | 🟡 Live, iterated with Timothy | https://koiiphish.github.io/AlgalBloom/ ("Algal Bloom Outlook"). "Clean marine" style, Inter, positron basemap; summary panel + More info; resizable panel; report-style wording; disclaimer in footer and panels (D015). Checkpoint: the live URL, reported together with Phases 1 and 4. |
| 6: Portfolio polish | 🟢 Built, awaiting review | README (why, how it works, Mermaid diagram, honest results, limitations, setup, next steps), screenshots + GIF (`tools/`), official management-plan map links, model card tidy-up, no licence (D018). Plus the earlier biomass wording and Verification page (D016). |

## Next steps

1. **Sign-off of Phases 1, 4, 5 and 6 is on hold** (Timothy, 24 Nov) until the PIRSA and theLIST replies arrive.
   - Non-technical summary: `docs/summary.md`, linked from the README.
2. **Verification:** the first satellite outcomes are due about 28 Nov (the 19 Nov outlook needs imagery to 26 Nov).
   - The Biotoxin News is fetched daily, but NRE has not published a new issue since 26 Oct.
3. **On hold (Timothy):** the request to NRE Tas for historical ShellMAP phytoplankton data.
4. **Optional (Timothy):** check the PALT "cumulative within a toxin group" wording (Biotoxin Management Plan, Appendix 3).
5. **Phase 6 (after sign-off):**
   - README with screenshots and an architecture diagram;
   - per-area ShellMAP management-plan map links (26 of 29 growing areas match);
   - tightening the model card's wording.
6. ✅ **Backed up 24 Nov:** the 202211 training history, `data/interim` and `data/features` were copied to `C:\Users\timne\AlgalBloom-backup\2026-11-24` (local copy only, Timothy's choice; 130 files, byte totals verified). Backups are **not** automatic.
7. ✅ **Town search** added (D017): a town name lists the harvest areas within 25 km, or the 3 nearest.

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
