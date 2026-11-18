"""SA Karenia case study (brief section 6): an out-of-region transfer test of the shipped forecast.

SA harvest-area polygons are not available yet (PIRSA), so we use 5 km circles around the three
SA IMOS NRS stations with phytoplankton counts (D012): Gulf St Vincent (GSV), Kangaroo Island
(KAI) and Upper Spencer Gulf (USG). For each circle:
  1. per-day OLCI chl (same extraction as Tasmania, pipeline.features.chl)
  2. clear-sky-weighted anomaly vs that circle's own 2016-2022 monthly baseline, and the same
     forward-window label (y = 1 above the circle's training 90th percentile)
  3. the shipped persistence score, mapped to probability and tier with the TASMANIAN
     calibration and cut-offs, unchanged (a genuine transfer: nothing is fitted on SA)
Then the forecast is compared with Karenia cell counts at the same station, with special
attention to the 2025 onset (first counts above the ShellMAP lab-alert level in May 2025).

Run:  uv run python -m pipeline.model.sa_transfer
Output: models/sa_transfer.json, docs/img/phase3_karenia_sa.png
"""

import glob
import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.features import target as T
from pipeline.features.areas import METRIC_CRS
from pipeline.features.chl import HISTORY_DIR, extract_file
from pipeline.features.chl_features import build_chl_features
from pipeline.labels.action_levels import EVENT_LEVELS, KARENIA_GROUP_LEVEL
from pipeline.labels.events import latest
from pipeline.model.calibrate import Calibrator
from pipeline.model.metrics import pr_auc
from pipeline.model.persistence import OUT_PATH as MODEL_PATH
from pipeline.model.persistence import SCORE
from pipeline.model.tiers import assign

STATIONS = {  # code: (name, lat, lon); coordinates from the NRS file (see events.csv)
    "GSV": ("Gulf St Vincent", -35.0230, 138.4600),
    "KAI": ("Kangaroo Island", -35.8322, 136.4473),
    "USG": ("Upper Spencer Gulf", -33.1110, 137.7080),
}
RADIUS_KM = 5.0
TEST_START = pd.Timestamp("2024-01-01")
OUT_JSON = REPO_ROOT / "models" / "sa_transfer.json"
OUT_FIG = REPO_ROOT / "docs" / "img" / "phase3_karenia_sa.png"


def station_circles(radius_km: float = RADIUS_KM) -> gpd.GeoDataFrame:
    """5 km circles around each station, in EPSG:4326, as pseudo harvest areas."""
    pts = gpd.GeoDataFrame(
        {"area_id": [f"sa:{c.lower()}" for c in STATIONS]},
        geometry=gpd.points_from_xy(
            [v[2] for v in STATIONS.values()], [v[1] for v in STATIONS.values()]
        ),  # fmt: skip
        crs=4326,
    )
    return (
        pts.to_crs(METRIC_CRS)
        .buffer(radius_km * 1000)
        .to_crs(4326)
        .to_frame("geometry")
        .assign(area_id=pts["area_id"].to_numpy())
    )


def sa_chl() -> pd.DataFrame:
    """Per-circle daily chl from the SA history boxes (a circle may sit in two boxes)."""
    circles = station_circles()
    files = sorted(glob.glob(str(HISTORY_DIR / "sa_*.nc")))
    df = pd.concat([extract_file(Path(f), circles) for f in files], ignore_index=True)
    df = df.sort_values("n_valid").drop_duplicates(["area_id", "date"], keep="last")
    missing = set(circles.area_id) - set(df.area_id)
    if missing:
        raise ValueError(f"circles not inside any SA box: {missing}")
    return df.sort_values(["area_id", "date"]).reset_index(drop=True)


def forecast_table(chl: pd.DataFrame) -> pd.DataFrame:
    """Weighted anomaly, label, persistence score, Tas-calibrated probability and tier."""
    base = T.add_log_chl(T.complete_daily_index(chl))
    tgt = T.add_target(T.add_anomaly(base, T.fixed_baseline(base)))
    feats = build_chl_features(tgt[["area_id", "date", "anomaly", "log_chl", "weight"]])
    df = tgt.merge(feats[["area_id", "date", SCORE]], on=["area_id", "date"], how="left")
    cfg = json.loads(MODEL_PATH.read_text())
    cal = Calibrator(**cfg["calibrator"])
    df["p"] = cal.predict(df[SCORE].to_numpy())
    df["tier"] = np.where(
        df["p"].notna(), assign(df["p"].fillna(0).to_numpy(), cfg["tier_cutoffs"]), "n/a"
    )
    return df


def karenia_counts() -> pd.DataFrame:
    """Karenia cells/L per SA station sample (genus file; 0 where counted but absent)."""
    nrs = pd.read_csv(latest("nrs_phyto_genus_*.csv"),
                      usecols=["StationCode", "SampleTime_Local", "Karenia"])  # fmt: skip
    nrs = nrs[nrs.StationCode.isin(list(STATIONS))].copy()
    nrs["date"] = pd.to_datetime(nrs.SampleTime_Local, format="ISO8601").dt.tz_localize(None)
    nrs["date"] = nrs["date"].dt.normalize()
    nrs["area_id"] = "sa:" + nrs.StationCode.str.lower()
    return nrs[["area_id", "date", "Karenia"]].fillna({"Karenia": 0.0})


def visit_scores(fc: pd.DataFrame, counts: pd.DataFrame, lookback: int = 7) -> pd.DataFrame:
    """Max probability/tier issued in the week before each sample, next to its Karenia count."""
    rows = []
    for r in counts.itertuples():
        w = fc[(fc.area_id == r.area_id) & (fc.date < r.date)
               & (fc.date >= r.date - pd.Timedelta(days=lookback))]  # fmt: skip
        p = w["p"].max()
        rows.append({"area_id": r.area_id, "date": r.date, "karenia": r.Karenia, "p_max": p})
    out = pd.DataFrame(rows)
    cfg = json.loads(MODEL_PATH.read_text())
    out["tier_max"] = np.where(
        out.p_max.notna(), assign(out.p_max.fillna(0).to_numpy(), cfg["tier_cutoffs"]), "n/a"
    )
    return out


def plot(fc: pd.DataFrame, counts: pd.DataFrame) -> None:
    """Per station, two aligned panels (no dual axis): forecast probability, and Karenia counts
    on a log scale with the lab-alert level, 2024 onwards."""
    cfg = json.loads(MODEL_PATH.read_text())
    cuts, alert = cfg["tier_cutoffs"], EVENT_LEVELS["Karenia"].lab_alert
    fig, axes = plt.subplots(6, 1, figsize=(9, 10), dpi=120, sharex=True,
                             gridspec_kw={"height_ratios": [2, 1.3] * 3})  # fmt: skip
    for i, (code, (name, _, _)) in enumerate(STATIONS.items()):
        aid, ax_p, ax_c = f"sa:{code.lower()}", axes[2 * i], axes[2 * i + 1]
        f = fc[(fc.area_id == aid) & (fc.date >= TEST_START)].set_index("date")["p"]
        ax_p.plot(f.index, f.to_numpy(), color="#2a78d6", lw=1.2, label="forecast probability")
        ax_p.axhline(cuts["high"], color="#d03b3b", lw=0.8, ls="--", label="High cut-off")
        ax_p.axhline(cuts["moderate"], color="#c98500", lw=0.8, ls="--", label="Moderate cut-off")
        ax_p.set_ylabel("probability")
        ax_p.set_title(f"{name} ({code})", fontsize=10, loc="left")
        c = counts[(counts.area_id == aid) & (counts.date >= TEST_START)]
        ax_c.scatter(c.date, c.Karenia.clip(lower=1), s=16, color="#eb6834", zorder=3,
                     label="Karenia cells/L (1 = none counted)")  # fmt: skip
        ax_c.axhline(alert, color="#52514e", lw=0.8, ls=":", label=f"lab-alert level ({alert:.0f})")
        ax_c.set_yscale("log")
        ax_c.set_ylim(0.5, 1e6)
        ax_c.set_ylabel("cells/L")
        for ax in (ax_p, ax_c):
            ax.spines[["top", "right"]].set_visible(False)
    axes[0].legend(frameon=False, fontsize=7, ncol=3, loc="upper left")
    axes[1].legend(frameon=False, fontsize=7, ncol=2, loc="upper left")
    fig.suptitle("SA transfer test: Tasmanian-calibrated persistence forecast vs Karenia counts",
                 fontsize=10)  # fmt: skip
    fig.tight_layout()
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG)


def _safe_pr_auc(lab: pd.DataFrame) -> float | None:
    """PR-AUC of the probability, or None when only one class is present."""
    if lab["y"].nunique() < 2:
        return None
    return float(pr_auc(lab["y"].to_numpy(), lab["p"].fillna(0).to_numpy()))


def _flag_rate(v: pd.DataFrame) -> float | None:
    """Share of samples whose preceding week reached Moderate or High (None if no samples)."""
    return float(v["tier_max"].isin(["Moderate", "High"]).mean()) if len(v) else None


def main() -> None:
    """Build the SA forecast, score it against labels and Karenia counts, save and plot."""
    fc = forecast_table(sa_chl())
    counts = karenia_counts()
    vs = visit_scores(fc, counts)
    lab_alert = EVENT_LEVELS["Karenia"].lab_alert
    res: dict = {"radius_km": RADIUS_KM, "lab_alert_cells_per_L": lab_alert,
                 "karenia_group_level": KARENIA_GROUP_LEVEL.lab_alert, "stations": {}}  # fmt: skip
    for aid, g in fc[fc.date >= TEST_START].groupby("area_id"):
        lab = g[g.y.notna()]
        v = vs[(vs.area_id == aid) & (vs.date >= TEST_START)]
        ev, non = v[v.karenia >= lab_alert], v[v.karenia < lab_alert]
        first_ev = ev.date.min()
        first_high = g[(g.tier == "High") & (g.date >= pd.Timestamp("2025-01-01"))].date.min()
        res["stations"][aid] = {
            "test_rows_labelled": int(len(lab)),
            "test_positive_rate": float(lab.y.mean()) if len(lab) else None,
            "test_pr_auc_persistence": _safe_pr_auc(lab),
            "samples_2024_on": int(len(v)),
            "karenia_samples_above_lab_alert": int(len(ev)),
            "hit_rate_moderate_or_high": _flag_rate(ev),
            "false_alarm_rate_moderate_or_high": _flag_rate(non),
            "first_karenia_above_lab_alert": str(first_ev.date()) if pd.notna(first_ev) else None,
            "first_high_tier_2025_on": str(first_high.date()) if pd.notna(first_high) else None,
            "max_karenia": float(v.karenia.max()) if len(v) else None,
        }  # fmt: skip
    res["visits"] = (
        vs[vs.date >= TEST_START]
        .assign(date=lambda d: d.date.dt.date.astype(str))
        .to_dict(orient="records")
    )
    OUT_JSON.write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    plot(fc, counts)
    print(pd.DataFrame(res["stations"]).T.to_string())
    print(vs[(vs.date >= TEST_START) & (vs.karenia > 0)].to_string())
    print(f"saved {OUT_JSON.relative_to(REPO_ROOT)}, {OUT_FIG.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
