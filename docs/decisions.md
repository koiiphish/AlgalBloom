# Decisions log

One short entry per non-obvious decision: context, choice, and the alternatives we rejected.

---

## D001 — Committed labels live in `labels/`, not `data/labels/` (2026-11-17)

**Context:** The brief says `data/` is git-ignored (raw caches). But the Phase 1 label archive (daily status snapshots) and `events.csv` must be committed, because the official status pages show only the current state and history is lost unless we record it.

**Choice:** Use a top-level `labels/` directory for every committed label file. `data/` stays purely for disposable, re-downloadable caches.

**Alternatives rejected:**
- *A `.gitignore` exception for `data/labels/`:* it works, but it mixes precious, irreplaceable data with throwaway caches in one tree. That makes an accidental `rm -rf data/` or a cache clean-up destructive.

## D002 — Exact version pins, and `pipeline` as an installable package (2026-11-17)

**Context:** The brief says to pin dependency versions. Notebooks run from `notebooks/`, so they can't import `pipeline` unless it is installed.

**Choice:** `pyproject.toml` uses exact `==` pins (and `uv.lock` pins every transitive dependency). Python is fixed to 3.12 via `.python-version` and `requires-python = ">=3.12,<3.13"`. `pipeline` is built with hatchling, and `uv sync` installs it in editable mode.

**Alternatives rejected:** `>=` ranges (not reproducible); `sys.path` hacks in notebooks (fragile and confusing for readers).

## D003 — Open-Meteo API use despite `Disallow: /` in its robots.txt (2026-11-17)

**Context:** robots.txt on `api.`, `archive-api.` and `marine-api.open-meteo.com` is `User-agent: * / Disallow: /`. Our rules say to check robots.txt.

**Choice:** Use the API. robots.txt governs crawlers indexing pages. Open-Meteo's terms explicitly offer the free API for programmatic non-commercial use, with call limits (10k/day). We stay far below them, send a descriptive User-Agent and batch requests.

**Alternatives rejected:** treating it as a ban (it contradicts the provider's own documented API terms); SILO only (needs a key, has no forecasts, so it can't drive a 7-day forecast).

**Contrast:** the AODN GeoServer also has `Disallow: /`, but we have *not* read AODN terms that explicitly invite scripted WFS use. So we treat it as off-limits and use a one-off manual portal download instead. If AODN documentation explicitly permits scripted WFS access, revisit this.

## D004 — Basemap: OpenFreeMap "liberty" style (2026-11-17)

**Context:** We need a free, keyless vector basemap for MapLibre.

**Choice:** OpenFreeMap (`https://tiles.openfreemap.org/styles/liberty`). It has no key, no limits and no cookies, commercial use is allowed, and MapLibre adds the required attribution automatically.

**Alternatives rejected:** MapTiler/Stadia/Mapbox (need API keys or accounts and have usage caps); raw OSM tile servers (their usage policy discourages use by third-party apps).

**Risk:** no SLA. Phase 5 will document a fallback style host.

## D005 — Near-real-time chlorophyll must not depend on IMOS (2026-11-17)

**Context:** IMOS VIIRS daily chl ran ~10 days (NOAA-20) to ~15 days (SNPP) behind real time on 2026-11-17. A 7-day forecast issued "today" can't wait that long for its most important input.

**Choice (provisional, pending the Copernicus test):** IMOS VIIRS for history and validation. Copernicus OLCI NRT (if its latency is ~1–2 days) for daily operation. Phase 2 must check that the two agree (bias and consistency), or train and predict on the same product.

**Alternatives rejected:** forecasting from 10-day-old chlorophyll (that turns a 7-day forecast into a ~17-day one and badly weakens the persistence signal).

**Update (2026-11-17, after the Copernicus test):** confirmed. **The primary chlorophyll source is Copernicus OLCI 300 m**: the multi-year L3 product (2016-04 →) for training, and the NRT L3 product (~2 days behind) for daily operation. That means training and prediction use the same sensor and algorithm family. 300 m also gives far better coverage of the small harvest areas (52/57 Tas areas with a pixel inside the polygon, vs 28/57 for IMOS 1 km). IMOS VIIRS stays as an independent cross-check (r ≈ 0.96–0.97 on log chl against OLCI) and as a backup if OLCI fails. Sentinel-3 OLCI starts in 2016, so the training period is ~2016-05 → 2022 (matching the brief's "Sentinel-3 era").

**Consequence for forecast drivers:** archived Copernicus physics forecasts only start in 2022-06. For training years before that, forecast drivers must be emulated with observed/analysis values, a limitation the brief already anticipates. It must be stated in the model card.

## D006 — Pin Copernicus dataset versions explicitly (2026-11-17)

**Context:** the toolbox picks a dataset's *default* version unless told otherwise. On 2026-11-17 the defaults for our main chl datasets are versions that **retire** soon (MY OLCI 300 m `202211` on 2026-11-24; NRT `202207`/`202411` on 2027-01-12). The replacement `202611` versions don't yet offer the ARCO subset service. If a version silently switches mid-project, the training and operational data can differ without our knowing.

**Choice:**
- Always pass `dataset_version=` explicitly in pipeline code, and record the version in output metadata.
- **Before the MY 300 m `202211` retirement on 2026-11-24, re-check** whether `202611` supports subsetting. If it doesn't, either download the SA/Tas history from `202211` before it goes (a one-off, small regional subset), or wait for `202611` ARCO, but don't mix versions without a bias check.
- Re-run the `describe` check at the start of Phase 2.

**Alternatives rejected:** relying on defaults (silent product changes = hidden data drift); bulk-downloading global `original-files` from `202611` now (very large for 300 m global, and wasteful).

## D007 — Option B: coastal-box OLCI 300 m history before the 202211 version retires (2026-11-17)

**Context:** the multi-year OLCI 300 m version `202211` retires on 2026-11-24 (D006). Phase 1 doesn't need chlorophyll history, but Phase 2 does. Downloading the full SA and Tas regional boxes would be ~26 GB (dry run).

**Choice:** download only coastal boxes around the growing areas (`pipeline/fetch/history_olci_300m.py`): 10 boxes, 16 deg², 2016-04-25 → 2026-11-09, variables `CHL`, `CHL_uncertainty`, `flags`. Dry-run estimate: 13 GB uncompressed. Files are saved per box per year with NetCDF compression, and the download can resume.
- **Tas boxes** come from the real ShellMAP polygons (dissolved by growing area, padded 0.15°, overlapping boxes merged).
- **SA boxes are provisional and hand-drawn** around the known regions (west coast bays, lower Eyre, Spencer Gulf, Yorke/GSV/KI north, Coorong), because PIRSA polygons aren't available. **When PIRSA's polygons arrive, check that every polygon plus its buffer lies inside a box.** Fetch any gap from version `202611` once it supports subsetting, after a bias check between versions.

**Alternatives rejected:** A, the full boxes (~26 GB; the disk is 90% full); C, waiting for `202611` subsetting (no date given, and it risks losing easy access to the history).

**Result (2026-11-17):** complete. All 110 box-year files (10 boxes × 2016–2026) downloaded with no errors and no missing days: 2016-04-25 → 2026-11-09 continuous, variables `CHL`, `CHL_uncertainty`, `flags`. **1.9 GB on disk** (13 GB uncompressed), in `data/raw/copernicus/history_olci_300m_v202211/` (git-ignored; reproducible with the script while version 202211 exists).

## D008 — Repo stays private for now; daily label commits by GitHub Actions (2026-11-17)

**Context:** the brief suggests a public repo (unlimited free Actions minutes). Timothy prefers private for now.

**Choice:** private. The Phase 1 jobs are tiny (`archive_status` ~1–2 min/day, `ci` a few minutes per push), well within the 2,000 free private minutes per month. The archiver commits new label rows to `main` daily as `github-actions[bot]`, so **pull before pushing** locally.

**Revisit:** before Phase 4 (heavier daily forecasts) and Phase 5 (GitHub Pages on a private repo needs a paid plan), so going public will be needed by Phase 5 at the latest.

## D009 — Label archive design choices (2026-11-17)

1. **At most one request per page per Hobart day, enforced in code.** `labels/raw/last_fetch.csv` records when each source was last requested, and the archiver skips a source already requested that Hobart day, even on manual re-runs. *Why:* the brief's scraping rule. The first run (from Timothy's machine, 01:15 Hobart 18 Nov) and the scheduled 21:00 UTC run (08:00 Hobart, the same day) would otherwise both have fetched.
2. **`reason` is "not stated in notice" for farmed areas.** The ShellMAP notice gives status and start time but never the cause. Tasmanian closures can be rainfall-driven as well as biotoxin-driven, so **a closure is not a HAB label by itself.** Reasons will come from cross-referencing the archived *Biotoxin News* (a later phase). Wild abalone block closures do state "for biotoxins", and those are captured.
3. **Fail loudly, but never lose data.** A hard parse failure appends nothing (exit 1). Softer problems (unknown area names, Biotoxin News failing) still append the good rows, then fail the job (exit 2), so GitHub emails Timothy. A parse is rejected if the strict parser and a loose header count disagree, which catches a new status label like the "NURSERY/SOURCE" label found during development.
4. **Event thresholds come from the published ShellMAP PALT** (Biotoxin Management Plan v6.1, Appendix 3), the *lab-alert* column. Our station data is mostly genus-level, so each genus uses its **lowest listed species level** (most precautionary; the PALT itself applies species levels to "sp./spp." reports). For ***Karenia*** that is the *K. brevis* level (500 cells/L) rather than the *Karenia/Karlodinium/Gymnodinium* group level (100,000), and `events.csv` flags both so the effect of the choice is visible. ***G. catenatum*** comes from the species file, because the genus *Gymnodinium* includes non-toxic species. The *P.-n. delicatissima* closure cell is ambiguous in the source table. We use the *seriata* group's levels, which are lower anyway.
5. **Tasmanian levels are applied to SA stations** as one consistent yardstick. SASQAP's own levels are unknown until PIRSA replies.

**Alternatives rejected:** treating every closure as a HAB event (it would mix rainfall closures into the labels); KKG-group levels for *Karenia* genus totals (they would hide the low-level 2018–2025 detections and the May 2025 onset); scraping Biotoxin News tables now (layout unverified; raw archiving is enough to stop losing history).

**Update (2026-11-18): the repo is now public** (Timothy's decision), which matches the brief's original recommendation. Effects:
- GitHub Actions minutes on standard runners are free and unlimited, and GitHub Pages (Phase 5) is available at no cost.
- Everything committed is now published. Checked before recording this: no `.env`, credentials or `data/` files have ever been committed, and all commits use the GitHub no-reply address.
- Published label data must keep its attribution. ShellMAP notices and Biotoxin News are reproduced under the Tasmanian Government **non-commercial** licence with acknowledgement (see `labels/README.md`). theLIST polygons stay unpublished until their licence is confirmed (only names are committed).
- GitHub may disable scheduled workflows in public repos after 60 days without repository activity. The daily bot commits should count as activity, but if `archive_status` ever stops, check whether the schedule was disabled (Actions tab → re-enable).

**Update to D006 (2026-11-18): processing boundary, drift and version comparison**
- **Boundary:** version 202211 is fully reprocessed ("my") from 2016-04-25 to 2021-12-31 and interim ("myint") from 2022-01-01 onwards (file names, via a `copernicusmarine.get` dry run).
- **Step check** (`docs` evidence from a box-median anomaly analysis of our history): there is no step in chlorophyll *level* at 2022-01-01 beyond normal year-to-year variation. Valid-pixel coverage dips in 2022 in both regions (about 7% in SA, 19% in Tas), probably a processing effect, and it is minor. **But Tas shows a steady decline 2022→2026** (median log10 anomaly −0.04 → −0.14, i.e. ~−28%) that SA does not.
- **Independent check, Maria Island (IMOS NRS in-situ surface chl, ship CTD fluorometer, ~10 samples/yr):** OLCI and in-situ agree broadly to 2021. From 2022 OLCI falls (−0.12 to −0.21) while in-situ rises (+0.21 to +0.69).
- **Version comparison** (`pipeline/fetch/recon_version_check.py`; two whole global 202611 days, cropped to the Tas boxes): **2019-01-21 is identical** (44,431 pixels; ratio 1.000). **2024-01-30: 202611 is ~10% lower than 202211** (43,101 pixels; median ratio 0.895; log10 p10–p90 −0.28 to −0.03). The new reprocessing therefore does **not** remove the post-2022 decline; it slightly deepens it.
- **Conclusions:** (1) the 2016–2021 training history is unaffected by the version change; (2) the operational (202611-family) data differs from our 2022+ history by ~10%, so **replace the 2022+ history with 202611 once it supports subsetting** (before final Phase 3 evaluation), or correct for the offset; (3) the satellite/in-situ divergence is **unexplained** (a real coastal change, an OLCI sensor-level issue, or fluorometer drift). It must be stated as a limitation, and it motivates evaluating the drift-resistant **trailing baseline** (option C) alongside the fixed one in the EDA.
- **Caveats:** two days and one in-situ station.

## D010 — Phase 2 driver sources: OSTIA SST, GLORYS12, ERA5 via Open-Meteo (2026-11-18)

**Context:** the Phase 2 plan named IMOS RAMSSA for SST, and noted that ocean-model features (mixed-layer depth, currents) might exist only from 2022-06 (analysis-forecast archive).

**Choice:**
- **SST: Copernicus OSTIA**, reprocessed (moi-00168, 1981 → 2026-06) spliced with near-real-time (moi-00165, 2024-01 → now). It is 0.05° (2× RAMSSA's resolution) and fast to subset, and its long record allows a **1991–2020 climatology** for SST anomaly and marine heatwaves, entirely before validation/test. REP vs NRT overlap (896 days, Tas box): mean difference 0.01 K, p5–p95 ±0.4 K, so splicing is safe. IMOS RAMSSA remains a cross-check.
- **Mixed-layer depth and currents: GLORYS12 reanalysis** (moi-00021, 1993 → 2026-10), the same 1/12° grid and model family as the operational analysis-forecast. This removes the "2022+ only" gap.
- **Weather: ERA5 via the Open-Meteo archive** (`models=era5`), one consistent reanalysis. Wind, radiation and air temperature come from the nearest **sea** cell (`cell_selection=sea`); precipitation comes from the nearest **land** cell (catchment runoff). Both parameters were verified by real requests (an invalid value returns HTTP 400). There are 13 distinct sea and 17 land cells for the 57 areas, downloaded at a pace of ≤4,000 call-units/hour (Open-Meteo counts >2 weeks of data per location as multiple calls).
- **Gridded products are matched to areas by the K=4 nearest valid ocean cells within 30 km**, and the mean distance is kept as a feature (SST cells: median 2.8 km, max 11 km; model cells: median 7.3 km, max 14 km).
- **Marine heatwave = SST above the 1991–2020 90th percentile for ≥5 consecutive days ending at t** (past-only form of Hobday et al. 2016). Sanity check: 24% of 2016 area-days are flagged, matching the documented 2015/16 Tasmanian marine heatwave.

**Note for Phase 3:** Open-Meteo's *Previous Runs API* archives the forecasts actually issued 1–7 days ahead, but mostly from **January 2024**. That's too late for training, but it covers the **test period**, so the final evaluation can use real issued forecasts as inputs. Pricing-page wording: the table marks the historical APIs ✅ for the free tier; an FAQ line saying they "require the Professional API Plan" reads as applying to paid plans (the Standard plan is ❌).

**Alternatives rejected:** RAMSSA as the main SST (coarser, slower OPeNDAP); the analysis-forecast archive for ocean features (starts 2022-06, so it can't cover training years); default "best match" Open-Meteo models (they mix ERA5 and IFS over time, so they are inconsistent across the record).
