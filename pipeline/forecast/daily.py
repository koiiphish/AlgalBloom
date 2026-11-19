"""The daily forecast job (Phase 4; run by .github/workflows/daily_forecast.yml).

Steps:
  1. issue date t = today in Hobart
  2. download ~18 days of OLCI NRT chl for the Tas harvest-area boxes; per-area daily stats
     with the training extraction code; merge into the archive (archive/chl_area_day.csv)
  3. score every area (pipeline.forecast.score), with evidence fields
  4. SST anomaly (OSTIA NRT vs 1991-2020 climatology): map layer + per-area context
  5. chlorophyll 7-day composite map layer for SA and Tasmania
  6. write the site; update the archive

Failure policy ("fail loudly", brief Phase 4):
  - chl input missing, or newest chl older than MAX_CHL_AGE_DAYS -> keep yesterday's site,
    mark it stale (status.json), exit 1
  - a map layer or SST context fails -> publish the forecast without it, list the problem in
    status.json, exit 2
GitHub emails the repo owner on any non-zero exit.

Run locally:  uv run python -m pipeline.forecast.daily --site _site [--previous prev_site]
(the scheduled job adds --archive)
"""

import argparse
import shutil
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import xarray as xr

from pipeline.config import SA_BBOX, TAS_BBOX
from pipeline.forecast import archive, area_pixels, inputs, score
from pipeline.forecast import sst as sstmod
from pipeline.model import deploy, sst_climatology
from pipeline.publish import rasters, site, web

MAX_CHL_AGE_DAYS = 4  # normal latency is 2 days (CHL_LAG_DAYS)
CHL_FETCH_DAYS = 18  # the whole NRT archive window; the score needs t-15 .. t-2
HISTORY_DAYS = 90
CHL_LAYER_TEXT = ("OLCI 300 m, 7-day median. Inshore values may be inflated by sediment and "
                  "dissolved organic matter.")  # fmt: skip


class Run:
    """Collects the problems of one run, so every failure ends up in status.json."""

    def __init__(self) -> None:
        self.problems: list[str] = []

    def note(self, what: str, err: Exception) -> None:
        """Record a non-fatal problem and print its traceback to the job log."""
        self.problems.append(f"{what}: {err}")
        print(f"PROBLEM {what}: {err}", file=sys.stderr)
        traceback.print_exc()


def hobart_today() -> pd.Timestamp:
    """Today's date in Tasmania (the issue date)."""
    return pd.Timestamp(datetime.now(ZoneInfo("Australia/Hobart")).date())


def chl_stats(
    issue: pd.Timestamp, work: Path, areas: area_pixels.AreaSet
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Download recent chl for the Tas boxes and extract per-area daily stats."""
    start = (issue - pd.Timedelta(days=CHL_FETCH_DAYS)).strftime("%Y-%m-%d")
    end = issue.strftime("%Y-%m-%d")
    parts, latest = [], []
    for box in areas.boxes:
        path = inputs.fetch_chl(box, start, end, work)
        parts.append(area_pixels.extract(path, areas))
        with xr.open_dataset(path) as ds:
            latest.append(pd.Timestamp(ds.time.values.max()).normalize())
    df = pd.concat(parts, ignore_index=True)
    df = df.sort_values("n_valid").drop_duplicates(["area_id", "date"], keep="last")
    missing = set(areas.area_ids) - set(df.area_id)
    if missing:
        raise inputs.InputError(f"{len(missing)} areas not inside any download box")
    return df, min(latest)


def map_layers(
    issue: pd.Timestamp, work: Path, out: Path, areas: area_pixels.AreaSet, run: Run
) -> tuple[dict, pd.Series | None]:
    """Chl composite and SST anomaly layers for both regions; per-area SST context (Tas)."""
    layers: dict = {"chl": {}, "sst_anomaly": {}}
    sst_area = None
    start7 = (issue - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    start_sst = (issue - pd.Timedelta(days=4)).strftime("%Y-%m-%d")
    end = issue.strftime("%Y-%m-%d")
    for region, box in (("tas", TAS_BBOX), ("sa", SA_BBOX)):
        try:
            p = inputs.fetch_chl(box, start7, end, work / "map")  # flags: land, for the lake mask
            lat, lon, vals, first, last = rasters.chl_composite(p)
            info = rasters.write_layer(vals, lat, lon, "chl", out / "rasters" / f"chl_{region}.png")
            info.update({"first_date": pd.Timestamp(first), "last_date": pd.Timestamp(last),
                         "description": CHL_LAYER_TEXT})  # fmt: skip
            layers["chl"][region] = info
        except Exception as e:  # noqa: BLE001 (a missing layer must not stop the forecast)
            run.note(f"chl layer {region}", e)
        try:
            p = inputs.fetch_sst(box, start_sst, end, work / "map")
            clim = sst_climatology.load(sst_climatology.out_path(region))
            lat, lon, anom, day = sstmod.anomaly_grid(p, clim)
            info = rasters.write_layer(
                anom, lat, lon, "sst", out / "rasters" / f"sst_anom_{region}.png"
            )
            info.update({"date": day, "description": "OSTIA SST relative to the 1991–2020 "
                         "daily mean."})  # fmt: skip
            layers["sst_anomaly"][region] = info
            if region == "tas":
                sst_area = sstmod.area_anomalies(lat, lon, anom, area_pixels.footprints(areas))
        except Exception as e:  # noqa: BLE001
            run.note(f"sst layer {region}", e)
    return layers, sst_area


def build_site(
    issue: pd.Timestamp, now: datetime, out: Path, work: Path, run: Run, save_archive: bool
) -> pd.DataFrame:
    """Steps 2-6 when the chl input is good. Returns today's forecasts.

    The archive is written only when `save_archive` (the scheduled job passes --archive), so
    local test runs never add rows that look like published forecasts.
    """
    dep = score.Deployment.load(deploy.OUT_PATH)
    areas = area_pixels.load()
    new, latest = chl_stats(issue, work, areas)
    age = (issue - latest).days
    if age > MAX_CHL_AGE_DAYS:
        raise inputs.InputError(f"newest chlorophyll is {age} days old ({latest.date()})")
    new = new.assign(source=f"nrt_{inputs.CHL_VERSION}",
                     retrieved_utc=now.isoformat(timespec="seconds"))  # fmt: skip
    chl = archive.upsert_chl(archive.load_chl(), new)
    today, history = score.run(chl, dep, areas.area_ids, issue, HISTORY_DAYS)
    layers, sst_area = map_layers(issue, work, out, areas, run)

    gj = site.areas_geojson(today, areas.meta, issue, dep.model_version, sst_area)
    site.write_json(out / "areas.geojson", gj)
    issued = archive.load_forecasts()
    fc = today.assign(issue_date=issue.strftime("%Y-%m-%d"), model_version=dep.model_version,
                      score=today[score.SCORE], data_latest_date=latest.strftime("%Y-%m-%d"),
                      run_utc=now.isoformat(timespec="seconds"))  # fmt: skip
    issued_all = archive.upsert_forecasts(issued, fc)
    for area_id in areas.area_ids:
        site.write_json(out / "timeseries" / site.ts_filename(area_id),
                        site.timeseries(history, issued_all, area_id))  # fmt: skip
    site.write_json(out / "layers.json", layers)
    tiers = today["tier"].value_counts().to_dict()
    site.write_json(out / "status.json", {
        "issue_date": issue, "valid_from": issue + pd.Timedelta(days=1),
        "valid_to": issue + pd.Timedelta(days=site.HORIZON),
        "run_utc": now.isoformat(timespec="seconds"), "model_version": dep.model_version,
        "stale": False, "stale_since": None, "problems": run.problems,
        "tier_cutoffs": dep.cutoffs,
        "inputs": {"chl_latest_date": latest, "chl_age_days": age,
                   "sst_date": layers["sst_anomaly"].get("tas", {}).get("date")},
        "tier_counts": {t: int(tiers.get(t, 0)) for t in ("Low", "Moderate", "High")},
        "stale_chl_areas": int(today["stale_chl"].sum()),
        "regions": {"tas": "forecast", "sa": "map layers only: SA harvest areas pending PIRSA"},
        "disclaimer": site.DISCLAIMER, "attribution": site.ATTRIBUTION,
    })  # fmt: skip
    if save_archive:
        archive.save(chl, issued_all)
    return fc


def publish_web(out: Path) -> None:
    """Add the web app and text pages next to the data files (Phase 5)."""
    web.build(out)
    (out / ".nojekyll").touch()  # serve files as-is on GitHub Pages


def main() -> int:
    """Run the job; returns the process exit code (0 ok, 1 stale, 2 partial)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True, help="output folder (gh-pages)")
    parser.add_argument("--previous", type=Path, default=None, help="yesterday's site, if any")
    parser.add_argument("--work", type=Path, default=inputs.DOWNLOAD_DIR)
    parser.add_argument("--archive", action="store_true", help="update archive/ (CI only)")
    args = parser.parse_args()
    now, issue, run = datetime.now(UTC), hobart_today(), Run()
    prev = args.previous if args.previous and args.previous.exists() else None
    if args.site.exists():
        shutil.rmtree(args.site)
    args.site.mkdir(parents=True)
    try:
        fc = build_site(issue, now, args.site, args.work, run, args.archive)
    except Exception as e:  # noqa: BLE001 (any failure here means "no trustworthy forecast")
        traceback.print_exc()
        shutil.rmtree(args.site)
        args.site.mkdir(parents=True)
        status = site.keep_previous(prev, args.site, f"{type(e).__name__}: {e}", now, issue)
        publish_web(args.site)
        print(f"HARD FAILURE: kept previous output, stale since {status['stale_since']}")
        return 1
    site.carry_history(prev, args.site, issue)
    publish_web(args.site)
    counts = fc["tier"].value_counts().to_dict()
    print(
        f"issue {issue.date()}: {len(fc)} areas {counts}; "
        f"mean p {np.nanmean(fc['p']):.3f}; problems: {len(run.problems)}"
    )
    return 2 if run.problems else 0


if __name__ == "__main__":
    sys.exit(main())
