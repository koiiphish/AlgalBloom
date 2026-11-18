"""Secondary evaluation (brief section 6): does the risk score line up with real harmful-species
cell counts? Tasmania has one IMOS NRS station, Maria Island (MAI), sampled ~monthly.

For every MAI sampling visit since the OLCI record starts, we look at the shipped persistence
forecast for the east-coast harvest areas within RADIUS_KM of the station, issued in the
LOOKBACK days before the visit (so it is a genuine forecast of the visit week):
  - hit rate:          share of EVENT visits (a taxon above its ShellMAP lab-alert level,
                       labels/events.csv) where the maximum tier was >= Moderate (or High)
  - false-alarm rate:  the same share for NON-event visits
  - lead time:         days between the first >= Moderate forecast in the lookback and the visit
Probabilities before 2023 use the 2023 calibration; that is fine for this descriptive check
(the calibrator is a monotone map, so ranks are unchanged).

Caveats: ~10 visits a year, one station ~25-40 km from the farms, surface/integrated samples,
and chlorophyll is a proxy that low-biomass toxic taxa (Alexandrium, Dinophysis) need not raise.

Run:  uv run python -m pipeline.model.secondary
Output: models/secondary_tas.json
"""

import json

import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.features.areas import METRIC_CRS, load_tas_areas
from pipeline.labels.events import EVENTS_PATH, latest
from pipeline.model import persistence as P
from pipeline.model.baselines import climatology_table
from pipeline.model.calibrate import Calibrator
from pipeline.model.data import load_table
from pipeline.model.tiers import assign

MAI_LAT, MAI_LON = -42.5967, 148.2333
RADIUS_KM, LOOKBACK = 40.0, 7
FIRST_VISIT = pd.Timestamp("2016-05-15")  # OLCI starts 2016-04-25, plus the 14-day score window
OUT_PATH = REPO_ROOT / "models" / "secondary_tas.json"
HIGH_BIOMASS = {"Karenia", "Pseudo-nitzschia", "Gymnodinium catenatum"}


def nearby_areas(radius_km: float = RADIUS_KM) -> list[str]:
    """Area IDs whose polygon lies within radius_km of the MAI station."""
    areas = load_tas_areas().to_crs(METRIC_CRS)
    station = gpd.GeoSeries(gpd.points_from_xy([MAI_LON], [MAI_LAT]), crs=4326).to_crs(METRIC_CRS)
    dist_km = areas.distance(station.iloc[0]) / 1000
    return areas.loc[dist_km <= radius_km, "area_id"].tolist()


def visits() -> pd.DataFrame:
    """MAI sampling dates, with whether any (and which) taxon exceeded its lab-alert level."""
    nrs = pd.read_csv(latest("nrs_phyto_genus_*.csv"), usecols=["StationCode", "SampleTime_Local"])
    dates = pd.to_datetime(nrs.loc[nrs.StationCode == "MAI", "SampleTime_Local"], format="ISO8601")
    v = pd.DataFrame({"date": sorted(set(dates.dt.tz_localize(None).dt.normalize()))})
    ev = pd.read_csv(EVENTS_PATH, parse_dates=["date"])
    ev = ev[ev.station_code == "MAI"].groupby("date")["taxon"].apply(lambda s: sorted(set(s)))
    v["taxa"] = v["date"].map(ev)
    v["event"] = v["taxa"].notna()
    v["high_biomass"] = v["taxa"].apply(
        lambda t: isinstance(t, list) and bool(HIGH_BIOMASS & set(t))
    )
    return v[v["date"] >= FIRST_VISIT].reset_index(drop=True)


def forecasts(df: pd.DataFrame, area_ids: list[str]) -> pd.Series:
    """Daily maximum probability over the nearby areas (issue-date index)."""
    cfg = json.loads(P.OUT_PATH.read_text())
    cal = Calibrator(**cfg["calibrator"])
    sub = df[df["area_id"].isin(area_ids)]
    p = P.predict(sub, cal, climatology_table(df))["p"]
    return p.groupby(sub["date"]).max()


def score_visits(v: pd.DataFrame, p_daily: pd.Series, cuts: dict[str, float]) -> pd.DataFrame:
    """Max probability/tier over the LOOKBACK issue dates before each visit, and lead time."""
    rows = []
    for d in v["date"]:
        window = p_daily[(p_daily.index >= d - pd.Timedelta(days=LOOKBACK)) & (p_daily.index < d)]
        tiers = assign(window.to_numpy(), cuts)
        flagged = window.index[tiers != "Low"]
        rows.append({
            "p_max": window.max(),
            "tier_max": assign(np.array([window.max()]), cuts)[0] if len(window) else "n/a",
            "lead_days": (d - flagged.min()).days if len(flagged) else np.nan,
        })  # fmt: skip
    return pd.concat([v, pd.DataFrame(rows)], axis=1)


def summarise(s: pd.DataFrame) -> dict:
    """Hit and false-alarm rates for >= Moderate and High."""
    out = {}
    for name, sel in [("all_events", s.event), ("high_biomass_events", s.high_biomass)]:
        ev, non = s[sel], s[~s.event]
        out[name] = {
            "n_event_visits": int(len(ev)),
            "n_non_event_visits": int(len(non)),
            "hit_rate_moderate_or_high": float((ev.tier_max != "Low").mean()),
            "hit_rate_high": float((ev.tier_max == "High").mean()),
            "false_alarm_rate_moderate_or_high": float((non.tier_max != "Low").mean()),
            "false_alarm_rate_high": float((non.tier_max == "High").mean()),
            "median_lead_days": float(ev.lead_days.median()),
            "mean_p_event": float(ev.p_max.mean()),
            "mean_p_non_event": float(non.p_max.mean()),
        }
    return out


def main() -> None:
    """Run the check and save a summary plus the per-visit table."""
    df = load_table()
    ids = nearby_areas()
    cuts = json.loads(P.OUT_PATH.read_text())["tier_cutoffs"]
    scored = score_visits(visits(), forecasts(df, ids), cuts)
    res = {"areas_within_km": RADIUS_KM, "areas": ids, "lookback_days": LOOKBACK,
           "summary": summarise(scored)}  # fmt: skip
    res["visits"] = scored.assign(date=scored.date.dt.date.astype(str)).to_dict(orient="records")
    OUT_PATH.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    names = sorted({a.split(":")[1] for a in ids})
    print(f"{len(ids)} areas within {RADIUS_KM:.0f} km of MAI: {names}")
    print(pd.DataFrame(res["summary"]).round(3).to_string())
    print(scored[scored.event][["date", "taxa", "p_max", "tier_max", "lead_days"]].to_string())
    print(f"saved {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
