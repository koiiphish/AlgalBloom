# CLAUDE.md — HAB Risk Forecaster (SA & Tasmania)

**Start of every session: read `docs/progress.md` (where we are, what's next). At the end of every session: update it.**

`PROJECT_BRIEF.md` is the source of truth. This file summarises the rules that apply to **every** session. If they ever conflict, the brief wins. Propose changes in `docs/decisions.md` instead of quietly deviating.

## What we're building
A free, public, static, map-based web app with a **7-day harmful algal bloom risk forecast** (Low / Moderate / High) for shellfish harvesting and aquaculture areas in **South Australia** and **Tasmania**, plus current satellite chlorophyll-a and SST anomaly layers. The users are aquaculture operators and portfolio reviewers, so the data science has to be rigorous and honestly evaluated.

## Hard constraints (never break these)
- **$0 running cost.** No paid services and no credit card anywhere. If a step could cost money (including AWS egress), **stop and tell Timothy**.
- **No always-on server.** Heavy work runs as scheduled GitHub Actions batch jobs. The site is static and only reads pre-computed files on GitHub Pages.
- **Free data only.** Record every licence in `docs/data_sources.md`, and attribute every source in the app footer and on the About page.
- **Secrets** (e.g. the Copernicus Marine login) live only in GitHub Actions secrets and a local `.env`. Never commit them, print them or log them.
- **Respectful scraping:** check robots.txt and the terms of use first. Send at most one request per status page per day, and set a descriptive User-Agent. If the terms forbid scraping, **stop and report**.
- **Safety disclaimer:** this is an experimental research tool, **not** a substitute for official SASQAP (SA) or ShellMAP (Tas) harvest decisions. Show it on the map and in every area popup.
- **Accounts:** say which account is needed and why **before** creating one or asking Timothy to.

## Stack (decided; change it only via a `docs/decisions.md` entry)
- Pipeline: Python 3.12, `uv`, xarray, rioxarray, geopandas, pandas, pyarrow, `copernicusmarine`, requests, scikit-learn, LightGBM/XGBoost, SHAP. **Pin versions.**
- Compute: GitHub Actions on standard runners (public repo), daily cron, **under ~15 min per daily run**.
- Outputs: small static files (GeoJSON, JSON time series, PNG/COG/PMTiles) force-pushed to `gh-pages` with only a rolling window of files.
- Training data: local Parquet. Raw downloads are cached in `data/` and **never committed**.
- Frontend: **plain HTML + CSS + vanilla JS (ES modules)** with MapLibre GL JS. **No React or other framework.** Vite only if needed. Keyless free basemap (e.g. OpenFreeMap; verify the terms). Small chart library (uPlot or Chart.js).
- Quality: pytest, ruff, and a CI workflow that runs the tests on every push.

## Data science rules
- **No leakage:** every feature must be available at issue time *t*. Forecast drivers for *t+1…t+7* come from **forecast** products. Where training has to use observed values instead, state that limitation explicitly.
- **Time-ordered splits only** (e.g. train ≤2022, validate 2023, test 2024–present). Keep the 2025–26 SA *Karenia* bloom as an out-of-sample case study.
- Climatology and thresholds are computed on **training years only**. Risk-tier cut-offs are chosen on **validation**, never on test.
- **Baselines must be reported and beaten:** persistence, seasonal climatology, and the Copernicus BGC chlorophyll forecast (thresholded the same way).
- Metrics are reported per region: PR-AUC, Brier score, reliability diagram, and recall at a fixed false-alarm rate. Use SHAP for global and per-prediction drivers.
- Be explicit that chlorophyll anomaly is a **proxy** for harmful blooms.
- Start with gradient boosting plus calibration. Try a sequence model only if it clearly helps afterwards.

## Working rules
- **Work one phase at a time** (see brief §8). At the end of each phase: run the tests, summarise what was built, list open questions and risks, then **stop and wait for review**. Don't run ahead.
- Before coding a phase, give a short plan (files, functions, risks). Wait for an OK if it changes anything in the brief.
- **Never invent** dataset IDs, URLs, variable names or licence terms. Verify them against the docs or a real request, and cite where you checked in `docs/data_sources.md`.
- If a source is unavailable, rate-limited, paid or forbids scraping, **stop and report with alternatives**. Don't quietly work around it.
- Prefer simple, readable code. Use type hints, docstrings and small functions in Python.
- Timothy is strong in Python, data science and marine biology, and weak in JS. **Comment every JS function in plain English.**
- Explain non-obvious decisions in code comments and in `docs/decisions.md` (context, choice, alternatives rejected).
- Commit in small, well-described steps.
- Notebooks are for exploration only. Logic lives in the `pipeline/` package.

## Layout
`pipeline/` (fetch, features, labels, model, publish) · `notebooks/` · `data/` (git-ignored caches only) · `labels/` (**committed** label archive: daily status snapshots, `events.csv`; see `docs/decisions.md`) · `models/` · `web/` · `docs/` · `tests/` · `.github/workflows/`
