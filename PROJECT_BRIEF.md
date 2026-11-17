# Build brief: Coastal Harmful Algal Bloom (HAB) Risk Forecaster — South Australia & Tasmania

> **How to use this file**
> 1. Create an empty **public** GitHub repo (public = free GitHub Actions minutes), clone it, and save this file in the repo root as `PROJECT_BRIEF.md`.
> 2. Open Claude Code in the repo and send:
>    *"Read PROJECT_BRIEF.md in full. Then create a CLAUDE.md that summarises the hard constraints and working rules from it, and start Phase 0. Stop at the Phase 0 checkpoint and wait for my review."*
> 3. Work one phase at a time. Don't let it run ahead.

---

## 1. Who I am and how to work with me

- I'm Timothy, a data professional with a BSc in Marine Biology & Aquaculture and an MSc in Computer Science (data science concentration). I spent five years in barramundi aquaculture (nursery management, then quality systems/compliance).
- **Strong:** Python, pandas, SQL, scikit-learn, PyTorch, Jupyter, Flask, statistics and ML evaluation, marine biology domain knowledge.
- **Weak:** JavaScript/React. I can read code but not write much of it. Keep the frontend simple, readable and heavily commented, with **no framework** (see the stack below).
- This is a learning and portfolio project, so **explain non-obvious decisions** briefly in comments and in `docs/decisions.md` (one short entry per decision: context, choice, alternatives rejected).

## 2. Product goal

A free, public, map-based web app that shows a **7-day harmful algal bloom risk forecast for coastal aquaculture areas** in **South Australia** (Spencer Gulf, Gulf St Vincent, Kangaroo Island, Eyre/Yorke Peninsulas) and **Tasmania** (shellfish and salmon growing areas), along with current satellite conditions.

**Primary users:** aquaculture operators (oysters, mussels, finfish) who want early warning. **Secondary:** employers reviewing my portfolio, so the data science must be rigorous and honestly evaluated.

**What a user should be able to do (MVP):**
1. Open a map of SA + Tasmania and see each shellfish harvesting area / aquaculture zone coloured by its **7-day risk tier** (Low / Moderate / High).
2. Click an area to see: the risk tier and probability, the main drivers behind it (e.g. "SST +2.1 °C above normal, chlorophyll rising 4 days running"), a 60–90-day time series of chlorophyll-a and SST, the date of the last data update, and a link to the **official** status page (SASQAP / ShellMAP).
3. Toggle background layers: latest chlorophyll-a, SST anomaly.
4. Read an "About & limitations" page and a model card.

**Non-goals for the MVP:** user accounts, push alerts or email, freshwater/inland blooms, states other than SA and Tasmania, mobile apps.

## 3. Hard constraints

- **$0 running cost.** No paid services, no credit card on file anywhere. If a step would incur a cost (including AWS data egress), stop and tell me.
- **No always-on server.** All heavy work runs as scheduled batch jobs. The website is static and only reads pre-computed files.
- **Free data only**, with licences recorded in `docs/data_sources.md`. Attribute every source in the app footer and About page.
- **Secrets** (e.g. Copernicus Marine login) live only in GitHub Actions secrets and a local `.env` that is git-ignored. Never commit them.
- **Respectful scraping:** check robots.txt and terms of use, send at most one request per page per day for status pages, and set a descriptive User-Agent. If terms forbid it, stop and tell me.
- **Safety disclaimer:** the app is an experimental research tool, **not** a substitute for official SASQAP (SA) or ShellMAP (Tasmania) harvest decisions. Show this on the map and in area popups.

## 4. Stack (decided; propose changes in `docs/decisions.md` before deviating)

| Layer | Choice | Why |
|---|---|---|
| Data + ML pipeline | Python 3.12, `uv` for env/deps, xarray, rioxarray, geopandas, pandas, pyarrow, `copernicusmarine` toolbox, requests, scikit-learn, LightGBM or XGBoost, SHAP | Matches my skills |
| Scheduling / compute | **GitHub Actions** (standard runners, public repo), daily cron | Free for public repos |
| Storage of outputs | Small static files: GeoJSON for areas + risk, JSON time series, PNG or Cloud-Optimised GeoTIFF / PMTiles for raster layers. Published to a `gh-pages` branch, force-pushed each run with only a rolling window of recent files so git history doesn't bloat | No database to host |
| Training data / history | Parquet files built locally (or in a free Colab notebook). Large raw downloads are cached locally and never committed | Keeps repo small |
| Frontend | **Plain HTML + CSS + vanilla JavaScript (ES modules)** with **MapLibre GL JS**, built with Vite only if needed. No React | I can read it and maintain it |
| Basemap | A free, keyless vector basemap (e.g. OpenFreeMap). Verify licence and terms in Phase 0 | $0, no API token |
| Charts | A small library such as uPlot or Chart.js, loaded from npm or a CDN | Simple |
| Hosting | **GitHub Pages** | Free |
| Tests / quality | pytest for the pipeline, ruff for lint/format, a GitHub Actions workflow that runs tests on every push | Portfolio quality |

## 5. Data sources to evaluate in Phase 0

Verify each one's **access method, licence, spatial/temporal resolution, coverage of SA + Tasmania, latency (how many days behind), and historical depth**. Record the results in `docs/data_sources.md`. Note anything that needs an account, and say so before creating one.

**Ocean colour / biology (target signal + features)**
- **Copernicus Marine Service**: Sentinel-3 OLCI ocean colour, global or regional chlorophyll-a. Check both the daily near-real-time L3/L4 products and the 300 m plankton product. Also check the **global biogeochemical analysis-forecast** product: it includes modelled chlorophyll forecasts, which make a strong baseline to beat. Free account required.
- **IMOS / AODN (Australian Ocean Data Network)**: IMOS ocean colour chlorophyll-a. Note that MODIS production ended in December 2024, so use **VIIRS (SNPP / NOAA-20+)** products for recent data. Licence CC BY 4.0.

**Physical drivers (features; forecasts are needed at prediction time for a 7-day horizon)**
- **Copernicus Marine global physics analysis-forecast**: SST, currents, salinity, mixed-layer depth, with a multi-day forecast.
- **IMOS SST** (e.g. multi-sensor L3S) for observed SST history.
- **Open-Meteo**: wind (speed/direction, important for upwelling and mixing), solar radiation, air temperature, rainfall; historical archive and 7–16-day forecast; marine API for waves. Free for **non-commercial** use, no key, about 10,000 calls/day. Confirm this project counts as non-commercial (it's free and has no revenue) and document that.
- **SILO** (Queensland Government): long daily climate records. Needs a free API key (an email address). Optional if Open-Meteo is enough.
- Optional: river discharge / rainfall runoff near outlets (e.g. Murray Mouth / Coorong for SA, Derwent and Huon for Tasmania). Evaluate free sources and keep only if easy.

**Ground truth / validation labels**
- **SA — PIRSA SASQAP**: harvesting area **maps and GPS boundaries** (use these as the prediction polygons) and the **current status of harvesting areas** (open/closed and the reason). Also PIRSA/SARDI harmful algal bloom situation updates and news releases about closures since the 2025 *Karenia* bloom.
- **Tasmania — NRE Tas ShellMAP**: harvest area status, and the weekly **"Biotoxin News"** with biotoxin and algal sampling results for growing areas. Harvest area boundaries from Tasmanian management plans or LIST spatial data (find what's available).
- **Australian Phytoplankton Database (AODN)**: historical cell counts by species, including harmful taxa (*Karenia*, *Alexandrium*, *Gymnodinium catenatum*, *Pseudo-nitzschia*, *Dinophysis*). Use it for validation and for building a historical event list.
- **IMOS AusCPR / National Reference Stations phytoplankton** where they overlap SA/Tasmania.

> **Key fact about labels:** the official status pages show only the *current* state. History disappears unless we record it. So Phase 1 starts a **daily snapshot archiver immediately**, even before the model exists.

## 6. Modelling approach (Option B: 7-day forecast)

**Prediction unit:** each harvesting area polygon (plus a 5–10 km coastal buffer, because satellite pixels near shore are unreliable). Optionally a coarse coastal grid for the background map.

**Primary target (dense, self-labelled), defined in `docs/target_definition.md`:**
For area *a* and issue date *t*: `y = 1` if the area's mean chlorophyll-a anomaly over days *t+1…t+7* exceeds a threshold relative to that area's own seasonal climatology (start with the 90th percentile for that calendar month, computed on training years only). Propose and justify the exact definition, and handle cloud gaps explicitly (gap-filled L4 vs. masked L3; minimum valid-pixel fraction).

**Secondary evaluation (sparse, real-world):** how well the risk score lines up with **official closures** and **harmful-species cell-count exceedances**. Report lead time, hit rate and false-alarm rate. Be explicit that chlorophyll anomalies are a *proxy*: not every high-chlorophyll event is harmful, and some harmful species bloom at low biomass.

**Features (all must be available at issue time *t*; no leakage):** recent chlorophyll level, trend and anomaly (lags 1–14 days); SST and SST anomaly; marine-heatwave indicator; wind speed/direction and an upwelling-favourable wind index for each gulf/coast; solar radiation; rainfall/runoff lags; current speed / residence-time proxy; mixed-layer depth; day-of-year (cyclical encoding); area ID or area-level static features. Forecast drivers for *t+1…t+7* come from the Copernicus / Open-Meteo **forecasts**, not observed future values. During training, emulate this honestly and document how (e.g. use archived forecasts if available, otherwise observed values with the limitation stated).

**Baselines (must be reported and beaten):** (1) persistence (today's anomaly state continues); (2) seasonal climatology; (3) Copernicus biogeochemistry chlorophyll forecast, thresholded the same way.

**Models:** start with gradient boosting (LightGBM/XGBoost) with probability calibration (isotonic or Platt). Only consider a sequence model (e.g. LSTM in PyTorch) after the boosted model is evaluated, and only if it clearly helps.

**Evaluation:** time-ordered splits only (e.g. train ≤2022, validate 2023, test 2024–present), with the 2025–26 SA *Karenia* event kept as a highlighted **out-of-sample case study**. Metrics: PR-AUC, Brier score, reliability diagram, recall at a fixed false-alarm rate, all per region. Show SHAP explanations globally and per prediction; the per-prediction top drivers feed the popup text.

**Risk tiers:** map calibrated probability to Low / Moderate / High. Choose the cut-offs from the validation set (not the test set) and document them.

**Deliverable:** `docs/model_card.md` covering intended use, data, target definition, metrics vs. baselines, known failure modes and limitations.

## 7. Repository layout (suggested)

```
.
├── PROJECT_BRIEF.md
├── CLAUDE.md
├── pipeline/            # Python package: fetch/, features/, labels/, model/, publish/
├── notebooks/           # exploration only; logic lives in pipeline/
├── data/                # git-ignored raw + interim caches
├── models/              # trained model artefacts (small) + metadata JSON
├── web/                 # static frontend (index.html, main.js, style.css)
├── docs/                # data_sources.md, decisions.md, target_definition.md, model_card.md
├── tests/
└── .github/workflows/   # ci.yml, archive_status.yml, daily_forecast.yml
```

## 8. Phases and checkpoints

At the end of **every** phase: run the tests, summarise what was built, list open questions and risks, and **stop and wait for my review**. Keep each phase small enough to review in one sitting.

**Phase 0 — Data reconnaissance.**
For each source in section 5, write a minimal fetch script that pulls one week of data for one SA and one Tasmanian area. Fill in `docs/data_sources.md` (access, licence, resolution, latency, history, gotchas). Get the SA harvesting area boundaries and find the Tasmanian equivalent. Confirm the basemap choice.
*Checkpoint:* a table of sources marked go / no-go, plus a map image (from a notebook) of the harvest polygons over a chlorophyll field.

**Phase 1 — Label archive (start early; it runs forever).**
Build `archive_status.yml`, a daily GitHub Action that snapshots the SASQAP and ShellMAP harvest area statuses into an append-only CSV (`date, region, area_id, status, reason, source_url, retrieved_at`) committed to the repo. Separately, compile a historical event table (`docs/` + `data/labels/events.csv`) from the Phytoplankton Database, the Tasmanian Biotoxin News archive (if accessible), and PIRSA closure announcements. Record provenance for every row.
*Checkpoint:* the action has run successfully, and there's a summary of how many historical events per region we have.

**Phase 2 — Feature dataset.**
Build area × day Parquet tables for the Sentinel-3 era (2016 onwards, or as far as the sources allow): target, features and data-quality flags. Write unit tests for the anomaly/climatology calculations and an explicit **leakage test** (no feature uses data after issue date *t*).
*Checkpoint:* EDA notebook with seasonal cycles, class balance per area, missing-data rates, and a plot of the 2025 SA event.

**Phase 3 — Model.**
Baselines first, then the boosted model, calibration, SHAP and the closure/cell-count validation. Write `docs/model_card.md`.
*Checkpoint:* the metrics table vs. baselines, reliability plot and *Karenia* case study. **I decide here whether the model is good enough to ship.**

**Phase 4 — Daily forecast pipeline.**
Build `daily_forecast.yml`: fetch the latest data and forecasts, build features, predict, and write `areas.geojson` (risk, probability, top drivers, timestamps), per-area `timeseries/*.json`, and raster layers. Publish to `gh-pages`. It must fail loudly (no silent stale data): if inputs are missing, keep yesterday's output but mark it stale with a timestamp.
*Checkpoint:* two consecutive successful scheduled runs.

**Phase 5 — Frontend.**
A MapLibre map of SA + Tasmania showing the risk-coloured polygons; a click popup with tier, probability, drivers, a chart and the official link; layer toggles; legend; "data as of" banner; disclaimer; About page and model card page. It should be mobile-friendly and work with keyboard navigation and colour-blind-safe colours. Comment every JS function in plain English.
*Checkpoint:* a live GitHub Pages URL.

**Phase 6 — Portfolio polish.**
README with screenshots/GIF, architecture diagram (Mermaid), "how it works" for non-experts, setup instructions, data attributions, limitations, and next steps (more states, alerts, archived-forecast retraining).

## 9. Working rules for Claude Code

- Before writing code for a phase, give me a short plan (files, functions, risks) and wait for an OK if the plan changes anything in this brief.
- Prefer simple, readable code over clever code. Type hints and docstrings in Python. Small functions.
- Never invent dataset IDs, URLs, variable names or licence terms. Verify them (docs or a real request) and cite where you checked in `docs/data_sources.md`.
- If a data source is unavailable, rate-limited, paid or forbids scraping, **stop and report** with alternatives. Don't quietly work around it.
- Pin dependency versions. Keep the GitHub Actions runtime per daily run under ~15 minutes.
- Commit in small, well-described steps.
