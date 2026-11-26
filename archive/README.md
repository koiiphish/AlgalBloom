# archive/

This folder is the daily forecast's own record, and it is **committed on purpose**. The near-real-time satellite product only keeps about 18 days, so anything needed later (checking forecasts, recalibrating, retraining) has to be saved as we go (design note D014, decision E).

Only the `daily_forecast` GitHub workflow writes to it (`pipeline/forecast/daily.py --archive`).

| File | What |
|---|---|
| `chl_area_day.csv` | One row per Tasmanian harvest area per day, with the columns below. The NRT product revises recent days, so the **latest retrieved value wins** for each area and date. |
| `forecasts.csv` | One row per issue date and area, as published, with the columns below. A same-day re-run replaces that day's rows; earlier days are never changed. |

**`chl_area_day.csv` columns**
- `chl`: median OLCI chlorophyll (mg m⁻³)
- `n_valid`, `n_pixels`: valid and total pixels in the area plus its 2 km buffer
- `chl_core`, `n_core`: the median and pixel count without cloud-edge pixels
- `source`: `my_202211` (seeded from the multi-year history) or `nrt_202207` (near-real-time)
- `retrieved_utc`: when the value was downloaded

**`forecasts.csv` columns**
- `score`: the 14-day clear-sky-weighted log10 chlorophyll anomaly
- `p`, `tier`: the forecast probability and its risk tier
- `stale_chl`: true when there was no clear view in the 14-day window
- `model_version`
- `data_latest_date`: the newest satellite day available at issue
- `run_utc`: when the job ran

Data: Generated using E.U. Copernicus Marine Service Information (OLCI chlorophyll, doi 10.48670/moi-00278 and 10.48670/moi-00280). Area definitions derive from theLIST © State of Tasmania; the polygons themselves are not stored here.
