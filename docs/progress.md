# Progress and handoff

**Read this first in every new session.** It says where the project stands and what happens next. Details live in `docs/decisions.md` (D001–D014), `docs/model_card.md` and `docs/data_sources.md`. Update this file at the end of every working session.

_Last updated: 2026-11-18_

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0: Data reconnaissance | ✅ Accepted | SA boundaries wait on PIRSA |
| 1: Label archive | 🟡 Built; checkpoint open | Waiting for successful scheduled `archive_status` runs (first real run 21:00 UTC 18 Nov) |
| 2: Feature dataset | ✅ Accepted (Tasmania) | SA features wait on PIRSA |
| 3: Model | ✅ Approved to ship | Calibrated chlorophyll persistence (D013); test scored once at commit `d881905`, never re-tune on it |
| 4: Daily forecast pipeline | 🟡 Built and pushed (`7363f6c`, D014) | Checkpoint: two consecutive successful scheduled `daily_forecast` runs |
| 5: Frontend | ⬜ Not started | |
| 6: Portfolio polish | ⬜ Not started | |

## Next steps

1. **Timothy:** add GitHub secrets `COPERNICUSMARINE_SERVICE_USERNAME` and `COPERNICUSMARINE_SERVICE_PASSWORD`.
2. Run `daily_forecast` (manually or at 22:00 UTC). After the first run, turn on Pages: Settings → Pages → branch `gh-pages`, root.
3. **Claude:** check the first two runs:
   - Did Pages rebuild after the token push?
   - What was `status.json` → `inputs.chl_age_days`?
   - Did the archive commit land on `main`?
4. Also confirm the Phase 1 `archive_status` runs succeeded.
5. Then report the Phase 4 checkpoint, and plan Phase 5 only after Timothy approves.

## Waiting on others

- **PIRSA (SASQAP):** SA harvest-area boundaries, and permission for one automated status read per day. `pir.sa.gov.au` returns 403 to scripts.
- **theLIST:** licence for ShellMAP Harvest Area Boundaries (layer 92). Until it's confirmed, publish **points only, never polygons**.

## Known issues and dates

- **2026-11-24:** the OLCI MY version 202211 (training history) retires. The local copy is in `data/` and is worth backing up.
- **2027-01-12:** the OLCI NRT version 202207 (the daily input) retires. Re-check the offset against the 202611 version before switching (D014).
- **Inland lakes** appear in the Tasmanian chlorophyll layer. Mask them in Phase 5.
- **Phase 4 commit message:** commit `7363f6c` also contains the deployment model file, the SST climatology and the archive seed, but its message doesn't say so.

## Standing reminders

- Run `git pull --rebase` before pushing, because bots commit to `main` daily.
- The repo is public, so treat every commit as published.
- uv lives at `/c/Users/timne/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe`. Add it to PATH in Git Bash.
- In Git Bash, heredocs with apostrophes fail. Write files with the editor tools instead.
