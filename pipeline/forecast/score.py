"""Score the persistence forecast from per-area daily chlorophyll stats (D013, D014).

This deliberately reuses the training code (pipeline.features.target and chl_features) so the
daily forecast is computed exactly as in Phase 3: same pixel rule, same clear-sky weights, same
fixed baseline, same 14-day window ending 2 days before the issue date. A unit test checks
that the daily path and the training path give identical scores on the same data.

Besides the score, each area gets plain-language "evidence" fields (decision C in D014): the
forecast has no weather or ocean drivers, so the popup explains it with the chlorophyll record
itself (how unusual, which way it is moving, how many clear views it rests on).
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.features import target as T
from pipeline.features.availability import CHL_LAG_DAYS
from pipeline.features.chl_features import LOOKBACK_DAYS, build_chl_features
from pipeline.model.calibrate import Calibrator
from pipeline.model.persistence import SCORE, predict
from pipeline.model.tiers import assign

WINDOW_DAYS = LOOKBACK_DAYS + CHL_LAG_DAYS  # calendar days before t that the score can touch
TREND_LOG10 = 0.1  # change in weighted-mean anomaly counted as rising/falling (~26%)


@dataclass(frozen=True)
class Deployment:
    """The frozen deployment file (models/forecast_tas.json) in usable form."""

    model_version: str
    calibrator: Calibrator
    cutoffs: dict[str, float]
    baseline: pd.DataFrame  # area_id, month, baseline (log10 chl)
    climatology: pd.DataFrame  # area_id, month, clim_rate
    min_valid_pixels: int

    @classmethod
    def load(cls, path: Path) -> "Deployment":
        """Read the deployment JSON."""
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            model_version=d["model_version"],
            calibrator=Calibrator(**d["calibrator"]),
            cutoffs=d["tier_cutoffs"],
            baseline=pd.DataFrame(d["baseline"]),
            climatology=pd.DataFrame(d["climatology_fallback"]),
            min_valid_pixels=d["min_valid_pixels"],
        )


def anomaly_table(
    chl: pd.DataFrame, dep: Deployment, area_ids: list[str], start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:  # fmt: skip
    """Complete daily calendar start..end for every area, with log chl, weight and anomaly.

    `chl` holds per-area daily stats (area_id, date, chl, n_valid, n_pixels). Days with no
    row (no data, or not downloaded) become cloudy days: NaN chl and weight 0.
    """
    days = pd.date_range(start, end, freq="D")
    idx = pd.MultiIndex.from_product([sorted(area_ids), days], names=["area_id", "date"])
    cols = ["chl", "n_valid", "n_pixels"]
    df = chl.set_index(["area_id", "date"])[cols].reindex(idx).reset_index()
    df = T.add_log_chl(df, dep.min_valid_pixels)
    return T.add_anomaly(df, dep.baseline)


def daily_scores(anoms: pd.DataFrame, dep: Deployment) -> pd.DataFrame:
    """Score, probability, tier and stale flag for every (area, date) in the table."""
    feats = build_chl_features(anoms[["area_id", "date", "anomaly", "log_chl", "weight"]])
    out = anoms[["area_id", "date", "anomaly", "weight"]].merge(
        feats[["area_id", "date", SCORE]], on=["area_id", "date"], how="left"
    )
    pred = predict(out, dep.calibrator, dep.climatology)
    out["p"] = pred["p"].to_numpy()
    out["stale_chl"] = pred["stale_chl"].to_numpy()
    out["tier"] = assign(out["p"].to_numpy(), dep.cutoffs)
    return out


def _wmean(g: pd.DataFrame) -> float:
    """Clear-sky-weighted mean anomaly of the rows with a finite anomaly (NaN if none)."""
    ok = g["anomaly"].notna() & (g["weight"] > 0)
    w = g.loc[ok, "weight"]
    return float((g.loc[ok, "anomaly"] * w).sum() / w.sum()) if w.sum() > 0 else np.nan


def evidence(anoms: pd.DataFrame, issue: pd.Timestamp) -> pd.DataFrame:
    """Per area: the chlorophyll record behind today's forecast, in plain terms.

    Window = the score's own window, t-15 .. t-2. The trend compares its newer half
    (t-8 .. t-2) with its older half (t-15 .. t-9).
    """
    last = issue - pd.Timedelta(days=CHL_LAG_DAYS)
    first = last - pd.Timedelta(days=LOOKBACK_DAYS - 1)
    split = last - pd.Timedelta(days=6)
    win = anoms[(anoms["date"] >= first) & (anoms["date"] <= last)]
    rows = []
    for area_id, g in win.groupby("area_id"):
        recent, prior = _wmean(g[g["date"] >= split]), _wmean(g[g["date"] < split])
        trend = recent - prior if np.isfinite(recent) and np.isfinite(prior) else np.nan
        word = (
            "unknown" if not np.isfinite(trend)
            else "rising" if trend >= TREND_LOG10
            else "falling" if trend <= -TREND_LOG10
            else "steady"
        )  # fmt: skip
        clear = g[g["log_chl"].notna()]
        last_clear = clear["date"].max() if len(clear) else pd.NaT
        rows.append({
            "area_id": area_id,
            "recent7_anom": recent,
            "prior7_anom": prior,
            "trend": word,
            "clear_days14": int(len(clear)),
            "mean_clear_fraction14": float(g["weight"].mean()),
            "last_clear_date": last_clear,
            "days_since_clear": (issue - last_clear).days if pd.notna(last_clear) else None,
        })  # fmt: skip
    return pd.DataFrame(rows)


def run(
    chl: pd.DataFrame, dep: Deployment, area_ids: list[str], issue: pd.Timestamp,
    history_days: int = 90,
) -> tuple[pd.DataFrame, pd.DataFrame]:  # fmt: skip
    """Today's forecast per area (with evidence) and the daily history for the time series."""
    start = issue - pd.Timedelta(days=history_days + WINDOW_DAYS)
    anoms = anomaly_table(chl, dep, area_ids, start, issue)
    daily = daily_scores(anoms, dep)
    today = daily[daily["date"] == issue].drop(columns=["anomaly", "weight"])
    today = today.merge(evidence(anoms, issue), on="area_id", how="left")
    today["anom_ratio"] = 10 ** today[SCORE]  # "x times the area's normal for this month"
    history = daily[daily["date"] > issue - pd.Timedelta(days=history_days)]
    return today.reset_index(drop=True), history.reset_index(drop=True)
