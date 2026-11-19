"""Write the static site files that the frontend reads (Phase 4; published to gh-pages).

  areas.geojson               one Point per Tasmanian harvest area (decision A, D014: polygons
                              stay unpublished until theLIST confirms the licence), with tier,
                              probability, evidence, SST context and the official status
  timeseries/<area>.json      last 90 days: daily chl anomaly, clear fraction, score,
                              probability and tier, plus what was actually issued each day
  layers.json + rasters/*.png chlorophyll 7-day composite and SST anomaly, SA and Tasmania
  status.json                 run time, data dates, stale flag, problems, attribution
  history/<date>/areas.geojson  rolling window of the last HISTORY_KEEP issue dates

"Fail loudly" (brief section 8, Phase 4): if the forecast inputs are missing, the previous
site is kept and status.json says it is stale, since when, and why.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.labels.shellmap import NOTICE_URL
from pipeline.model.persistence import SCORE

HISTORY_KEEP = 7
SNAPSHOTS = REPO_ROOT / "labels" / "status_snapshots.csv"
HORIZON = 7
DISCLAIMER = (
    "Experimental research tool. Indicates chlorophyll-a (algal biomass), not toxins or "
    "harmful species. Not a substitute for official harvest decisions by ShellMAP (Tasmania) "
    "or SASQAP (South Australia)."
)
ATTRIBUTION = [
    {"text": "Generated using E.U. Copernicus Marine Service Information",
     "dois": ["https://doi.org/10.48670/moi-00278", "https://doi.org/10.48670/moi-00280",
              "https://doi.org/10.48670/moi-00165", "https://doi.org/10.48670/moi-00168"]},
    {"text": "Harvest-area status: © State of Tasmania (NRE Tas, ShellMAP)", "url": NOTICE_URL},
    {"text": "Harvest-area locations derived from theLIST, © State of Tasmania",
     "url": "https://www.thelist.tas.gov.au/"},
]  # fmt: skip
OFFICIAL_LINKS = {"tas": NOTICE_URL}


def ts_filename(area_id: str) -> str:
    """Safe file name for an area's time series, e.g. tas__moulting_bay__zone_1.json."""
    return area_id.replace(":", "__") + ".json"


def write_json(path: Path, obj) -> None:
    """Compact UTF-8 JSON (NaN written as null)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(obj), separators=(",", ":"), ensure_ascii=False),
                    encoding="utf-8")  # fmt: skip


def _clean(o):
    """Make an object JSON-safe: NaN/NaT -> None, numpy/pandas scalars -> Python, dates -> ISO."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_clean(v) for v in o]
    if isinstance(o, pd.Timestamp):
        return None if pd.isna(o) else o.strftime("%Y-%m-%d")
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float):
        return None if not np.isfinite(o) else round(o, 4)
    if o is pd.NaT:
        return None
    return o


def area_points(areas: gpd.GeoDataFrame) -> pd.DataFrame:
    """One representative point per area (always inside the polygon), rounded to ~100 m."""
    pts = areas.to_crs(28355).representative_point().to_crs(4326)
    return pd.DataFrame({"area_id": areas["area_id"].to_numpy(),
                         "lon": pts.x.round(3).to_numpy(), "lat": pts.y.round(3).to_numpy(),
                         "harvest_area": areas["harvest_area"].to_numpy(),
                         "growing_area": areas["growing_area"].to_numpy(),
                         "match_key": areas["match_key"].to_numpy()})  # fmt: skip


def official_status(path: Path = SNAPSHOTS) -> pd.DataFrame:
    """Latest archived official status per area (match_key), from the Phase 1 label archive."""
    if not path.exists():
        return pd.DataFrame(columns=["match_key", "official_status", "official_status_since",
                                     "official_snapshot_date"])  # fmt: skip
    from pipeline.labels.tas_lookup import match_key

    s = pd.read_csv(path)
    s = s[s["region"] == "tas"].sort_values("date").drop_duplicates("area_id", keep="last")
    return pd.DataFrame({"match_key": s["area_id"].map(match_key),
                         "official_status": s["status"],
                         "official_status_since": s["status_since"],
                         "official_snapshot_date": s["date"]})  # fmt: skip


def areas_geojson(today: pd.DataFrame, points: pd.DataFrame, issue: pd.Timestamp,
                  model_version: str, sst: pd.Series | None) -> dict:  # fmt: skip
    """The forecast as a GeoJSON FeatureCollection of points."""
    df = points.merge(today, on="area_id", how="left")
    df = df.merge(official_status(), on="match_key", how="left")
    valid = [issue + pd.Timedelta(days=1), issue + pd.Timedelta(days=HORIZON)]
    feats = []
    for r in df.itertuples(index=False):
        props = {
            "area_id": r.area_id, "region": "tas", "harvest_area": r.harvest_area,
            "growing_area": r.growing_area, "issue_date": issue, "valid_from": valid[0],
            "valid_to": valid[1], "tier": r.tier, "probability": r.p,
            "stale_chl": bool(r.stale_chl),
            "evidence": {
                "chl_vs_normal_ratio": r.anom_ratio, "score_log10_anomaly": getattr(r, SCORE),
                "trend": r.trend, "recent7_log10_anomaly": r.recent7_anom,
                "prior7_log10_anomaly": r.prior7_anom, "clear_days_of_14": r.clear_days14,
                "mean_clear_fraction": r.mean_clear_fraction14,
                "last_clear_date": r.last_clear_date, "days_since_clear": r.days_since_clear,
            },
            "context": {
                "sst_anomaly_c": None if sst is None else sst.get(r.area_id),
                "note": "Context only: sea temperature is not used by this forecast.",
            },
            "official": {"status": r.official_status, "since": r.official_status_since,
                         "snapshot_date": r.official_snapshot_date,
                         "url": OFFICIAL_LINKS["tas"]},
            "timeseries": f"timeseries/{ts_filename(r.area_id)}",
            "geometry_note": "Point location; harvest-area boundaries not yet published "
                             "(licence pending).",
            "disclaimer": DISCLAIMER,
        }  # fmt: skip
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]}})  # fmt: skip
    return {"type": "FeatureCollection", "model_version": model_version,
            "issue_date": issue, "features": feats}  # fmt: skip


def timeseries(history: pd.DataFrame, issued: pd.DataFrame, area_id: str) -> dict:
    """One area's last 90 days. `p`/`tier` are recomputed with today's (possibly revised)
    data; `issued_p`/`issued_tier` are what the site actually showed that day (null before
    the daily job started)."""
    h = history[history["area_id"] == area_id].sort_values("date")
    iss = issued[issued["area_id"] == area_id].set_index("issue_date")
    dates = h["date"].dt.strftime("%Y-%m-%d").tolist()
    return {
        "area_id": area_id,
        "dates": dates,
        "chl_log10_anomaly": h["anomaly"].tolist(),
        "clear_fraction": h["weight"].tolist(),
        "score": h[SCORE].tolist(),
        "p": h["p"].tolist(),
        "tier": h["tier"].tolist(),
        "issued_p": [iss["p"].get(d) for d in dates],
        "issued_tier": [iss["tier"].get(d) for d in dates],
    }


def carry_history(prev: Path | None, site: Path, issue: pd.Timestamp | None) -> None:
    """Copy the previous dated snapshots, add today's, keep only the newest HISTORY_KEEP."""
    hist = site / "history"
    if prev is not None and (prev / "history").exists():
        shutil.copytree(prev / "history", hist, dirs_exist_ok=True)
    if issue is not None and (site / "areas.geojson").exists():
        day = hist / issue.strftime("%Y-%m-%d")
        day.mkdir(parents=True, exist_ok=True)
        shutil.copy2(site / "areas.geojson", day / "areas.geojson")
    if hist.exists():
        for old in sorted(p for p in hist.iterdir() if p.is_dir())[:-HISTORY_KEEP]:
            shutil.rmtree(old)


def keep_previous(prev: Path | None, site: Path, reason: str, now: datetime,
                  issue: pd.Timestamp) -> dict:  # fmt: skip
    """Inputs failed: republish yesterday's files unchanged, with a stale status.json."""
    status: dict = {}
    if prev is not None and (prev / "status.json").exists():
        for item in prev.iterdir():
            if item.name == ".git":
                continue
            dest = site / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
        status = json.loads((prev / "status.json").read_text(encoding="utf-8"))
    since = status.get("stale_since") or status.get("run_utc") or now.isoformat(timespec="seconds")
    status.update({
        "stale": True, "stale_since": since, "stale_reason": reason,
        "last_attempt_utc": now.isoformat(timespec="seconds"),
        "attempted_issue_date": issue, "disclaimer": DISCLAIMER, "attribution": ATTRIBUTION,
    })  # fmt: skip
    write_json(site / "status.json", status)
    return status
