# Progress and handoff

**Read this first in every new session.** It says where the project stands and what happens next. Details live in `docs/decisions.md` (D001–D018), `docs/model_card.md` and `docs/data_sources.md`. Update this file at the end of every working session.

_Last updated: 2026-11-24_

## Phase status

All six phases are built. **Timothy is holding sign-off until PIRSA and theLIST reply** (24 Nov).

| Phase | Status | Notes |
|---|---|---|
| 0: Data reconnaissance | ✅ Accepted | SA boundaries wait on PIRSA |
| 1: Label archive | 🟢 Checkpoint met; sign-off on hold | 7 green scheduled `archive_status` runs (18–24 Nov); 1 status change captured (Triabunna Zone B, Open → Closed, 23 Nov) |
| 2: Feature dataset | ✅ Accepted (Tasmania) | SA features wait on PIRSA |
| 3: Model | ✅ Approved to ship | Calibrated chlorophyll persistence (D013); deployed as `persistence-1.1` after one recalibration (D014). The test was scored once at commit `d881905`; never re-tune on it. |
| 4: Daily forecast pipeline | 🟢 Checkpoint met; sign-off on hold | 5 consecutive green scheduled runs (20–24 Nov). Data age is 2 days every day; no stale areas. Runs start 2–8 h after the 22:17 UTC schedule (GitHub queue). |
| 5: Frontend | 🟢 Live; sign-off on hold | https://koiiphish.github.io/AlgalBloom/ ("Algal Bloom Outlook"). Biomass wording, summary panel + More info, resizable panel, town search within 25 km (D017), official map links (D018), disclaimer in the footer and panels (D015–D016) |
| 6: Portfolio polish | 🟢 Built; sign-off on hold | README (why, Mermaid diagram, honest results, setup, next steps), screenshots + GIF (`tools/`), Non-technical summary (`docs/summary.md`), Verification page (D016), model card tidy-up, no licence: all rights reserved (D018) |

## Next steps

1. **Waiting on replies (Timothy):**
   - **PIRSA:** unlocks SA area outlooks (boundaries + one daily status read).
   - **theLIST:** unlocks real area outlines instead of points.
   - Then sign off Phases 1, 4, 5 and 6.
2. **About 28 Nov (Claude):** check that the first satellite outcomes appear correctly on the Verification page. The 19 Nov outlook needs imagery to 26 Nov.
3. **Weekly (automatic):** Biotoxin News issues are matched against the outlooks. NRE has not published a new issue since 26 Oct.
4. **Before 12 Jan 2027 (hard deadline):** the daily OLCI NRT version 202207 retires. Check the 202611 replacement for an offset (it read about 10% lower in the D006 test), then switch the pinned version (D014).
5. **About Nov 2027:** with a year of published outlooks archived, recalibrate on a rolling window and score the model on its live record.
6. **Optional (Timothy):**
   - send the NRE Tas request for historical ShellMAP phytoplankton data (on hold);
   - check the PALT "cumulative within a toxin group" wording (Biotoxin Management Plan, Appendix 3);
   - copy `C:\Users\timne\AlgalBloom-backup` off the laptop;
   - choose a code licence if reuse is ever wanted.

**Done 24 Nov:**
- training-history backup (local copy, verified; backups are **not** automatic);
- town search;
- management-plan map links;
- README, screenshots and GIF;
- Non-technical summary;
- `CLAUDE.md` rule to list unknowns before every answer;
- answers end with an "80/20" section (memory note).

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
- **2026-11-24:** the OLCI MY version 202211 (training history) retired. Local copy in `data/`, backed up to `C:\Users\timne\AlgalBloom-backup\2026-11-24`.
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
