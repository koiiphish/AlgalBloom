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
