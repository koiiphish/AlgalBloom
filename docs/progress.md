# Progress and handoff

**Read this first in every new session.** It says where the project stands and what happens next. Details live in `docs/decisions.md` (D001–D015), `docs/model_card.md` and `docs/data_sources.md`. Update this file at the end of every working session.

_Last updated: 2026-11-19_

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0: Data reconnaissance | ✅ Accepted | SA boundaries wait on PIRSA |
| 1: Label archive | 🟡 Built; checkpoint open | Scheduled `archive_status` run #2 succeeded on 19 Nov (commit `9f7f918`). Confirm one more, then report the checkpoint. |
| 2: Feature dataset | ✅ Accepted (Tasmania) | SA features wait on PIRSA |
| 3: Model | ✅ Approved to ship | Calibrated chlorophyll persistence (D013); test scored once at commit `d881905`, never re-tune on it |
| 4: Daily forecast pipeline | 🟡 Working (manual run green 19 Nov; archive commit `d1ff6a2`) | Checkpoint: two consecutive green **scheduled** `daily_forecast` runs (22:17 UTC) |
| 5: Frontend | 🟡 Built (D015), pending Timothy's review | Live at https://koiiphish.github.io/AlgalBloom/ once `publish_web` runs. Checkpoint: the live URL. |
| 6: Portfolio polish | ⬜ Not started | |

## Next steps

1. ✅ All three secrets added, and Pages is on (`gh-pages`, root) as of 19 Nov.
2. **Timothy:** click through the live site on desktop and phone (map, list, panel, layers, About, Model card) and give feedback.
3. **Claude:** check the scheduled runs via the public API (`curl https://api.github.com/repos/koiiphish/AlgalBloom/actions/runs`, and `status.json` from raw.githubusercontent `gh-pages`):
   - Did Pages rebuild?
   - What was `status.json` → `inputs.chl_age_days`?
   - Did the archive commit land?
4. Then report the Phase 1, 4 and 5 checkpoints. Phase 6 only after approval.

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

- **2026-11-24:** the OLCI MY version 202211 (training history) retires. The local copy is in `data/` and is worth backing up.
- **2027-01-12:** the OLCI NRT version 202207 (the daily input) retires. Re-check the offset against the 202611 version before switching (D014).
- **Inland lakes** appear in the Tasmanian chlorophyll layer. Mask them in Phase 5.
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
