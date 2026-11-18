"""Compare valid-day rules for the chlorophyll target (D011 update; train years only).

Partly cloudy days make the per-area daily median noisy. The candidates are:
  px5          >= 5 valid pixels (the original rule)
  frac25/50    >= 25% / 50% of the area's pixels valid
  core         cloud-edge pixels removed (chl_core), >= 5 core pixels
  core_frac25  core median, and >= 25% of the area's pixels valid
  weighted     px5, but each day weighted by its valid fraction in every window mean
  core_wtd     core median, weighted by valid fraction

Pre-stated selection rule (before looking at results): highest mean PR-AUC lift
(PR-AUC / positive rate) of a fixed small LightGBM over rolling-origin years 2018-2022
(fit on all earlier years), provided >= 25% of training issue dates are labelled. Ties go
to more coverage. Validation (2023) and test (2024+) are not used.

Run:  uv run python -m pipeline.features.valid_day_compare
"""

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from pipeline.features import target as T
from pipeline.features.availability import CHL_LAG_DAYS
from pipeline.features.build import OUT_PATH as TABLE_PATH
from pipeline.features.chl import OUT_PATH as CHL_PATH
from pipeline.model.metrics import pr_auc

YEARS = [2018, 2019, 2020, 2021, 2022]
MIN_LABELLED = 0.25
LGB_PARAMS = {
    "objective": "binary", "learning_rate": 0.03, "num_leaves": 7, "min_child_samples": 1000,
    "lambda_l2": 10.0, "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1,
    "verbosity": -1, "seed": 1, "num_threads": 4, "deterministic": True,
}  # fmt: skip
N_TREES = 200


@dataclass(frozen=True)
class Rule:
    """One valid-day rule."""

    name: str
    chl_col: str
    n_col: str
    min_frac: float = 0.0
    weighted: bool = False


RULES = [
    Rule("px5", "chl", "n_valid"),
    Rule("frac25", "chl", "n_valid", 0.25),
    Rule("frac50", "chl", "n_valid", 0.50),
    Rule("core", "chl_core", "n_core"),
    Rule("core_frac25", "chl_core", "n_core", 0.25),
    Rule("weighted", "chl", "n_valid", weighted=True),
    Rule("core_wtd", "chl_core", "n_core", weighted=True),
]


def _wmean(a: pd.Series, w: pd.Series, window: int, shift: int) -> tuple[pd.Series, pd.Series]:
    """Weighted mean and count of valid values over a window ending `shift` days ago (past),
    or starting tomorrow if shift < 0 (the forward window t+1..t+window)."""
    aw, ww = (a * w).fillna(0.0), w.where(a.notna(), 0.0)
    cnt = a.notna().astype(float)
    if shift < 0:  # forward: reverse, roll, reverse (as target.forward_window)
        f = [x.shift(-1)[::-1].rolling(window, min_periods=1).sum()[::-1] for x in (aw, ww, cnt)]
    else:
        f = [x.shift(shift).rolling(window, min_periods=1).sum() for x in (aw, ww, cnt)]
    mean = f[0] / f[1].where(f[1] > 0)
    return mean, f[2]


def labels_and_persistence(chl: pd.DataFrame, rule: Rule) -> pd.DataFrame:
    """Anomaly, label and simple chl features for one rule (fixed baseline, train-only
    climatology and threshold, as in docs/target_definition.md)."""
    cols = ["area_id", "date", rule.chl_col, rule.n_col, "n_valid", "n_pixels"]
    d = chl[list(dict.fromkeys(cols))].copy()  # de-duplicated (px5 uses n_valid twice)
    frac = d["n_valid"] / d["n_pixels"]
    n = d[rule.n_col].where(frac >= rule.min_frac, 0)
    d = d.assign(chl=d[rule.chl_col], n_valid=n)[["area_id", "date", "chl", "n_valid"]]
    d["frac"] = frac
    base = T.add_log_chl(T.complete_daily_index(d))
    anom = T.add_anomaly(base, T.fixed_baseline(base))
    out = []
    for _, g in anom.sort_values(["area_id", "date"]).groupby("area_id", sort=False):
        a = g["anomaly"]
        w = g["frac"].fillna(0.0) if rule.weighted else pd.Series(1.0, index=g.index)
        f = pd.DataFrame({"area_id": g["area_id"], "date": g["date"], "anomaly": a})
        f["fwd_mean"], f["fwd_n"] = _wmean(a, w, T.HORIZON_DAYS, -1)
        for win in (7, 14):
            f[f"p_mean{win}"], f[f"p_n{win}"] = _wmean(a, w, win, CHL_LAG_DAYS)
        f["p_last"] = a.shift(CHL_LAG_DAYS).ffill(limit=14)
        out.append(f)
    f = pd.concat(out)
    f.loc[f["fwd_n"] < T.MIN_VALID_DAYS, "fwd_mean"] = np.nan
    f["month"] = f["date"].dt.month
    last_train = T.TRAIN_END - pd.Timedelta(days=T.HORIZON_DAYS)
    tr = f[f["date"] <= last_train]
    thr = tr.groupby(["area_id", "month"])["fwd_mean"].quantile(T.QUANTILE).rename("thr")
    f = f.join(thr, on=["area_id", "month"])
    ok = f["fwd_mean"].notna() & f["thr"].notna()
    f["y"] = np.where(ok, (f["fwd_mean"] > f["thr"]).astype(float), np.nan)
    return f


def noise_stats(f: pd.DataFrame) -> dict[str, float]:
    """Lag-1 correlation of daily anomaly and lag-9 correlation of the window mean (train)."""
    t = f[f["date"] <= T.TRAIN_END].sort_values(["area_id", "date"])
    g = t.groupby("area_id")
    return {
        "daily_lag1_corr": t["anomaly"].corr(g["anomaly"].shift(1)),
        "window_lag9_corr": t["fwd_mean"].corr(g["fwd_mean"].shift(9)),
    }


def rolling_lift(f: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    """Per-year PR-AUC lift of persistence and a small LightGBM (fit on earlier years)."""
    chl_feats = ["p_last", "p_mean7", "p_mean14", "p_n7", "p_n14"]
    x = f.merge(other, on=["area_id", "date"], how="left")
    feats = chl_feats + [c for c in other.columns if c not in ("area_id", "date")]
    lab = x[x["y"].notna()]
    rows = []
    for year in YEARS:
        tr = lab[lab["date"] <= pd.Timestamp(f"{year - 1}-12-24")]
        te = lab[(lab["date"].dt.year == year) & (lab["date"] <= pd.Timestamp(f"{year}-12-24"))]
        y, base = te["y"].to_numpy(), te["y"].mean()
        model = lgb.train(LGB_PARAMS, lgb.Dataset(tr[feats], tr["y"]), N_TREES)
        rows.append({
            "year": year,
            "persistence_lift": pr_auc(y, te["p_mean14"].fillna(0).to_numpy()) / base,
            "model_lift": pr_auc(y, model.predict(te[feats])) / base,
        })  # fmt: skip
    return pd.DataFrame(rows).set_index("year")


def non_chl_features() -> pd.DataFrame:
    """Weather, SST/ocean, season and static features from the Phase 2 table."""
    df = pd.read_parquet(TABLE_PATH)
    drop_prefix = ("chl_", "anomaly_", "fwd_", "threshold_", "y_")
    drop = {"log_chl", "n_valid", "processing", "split", "match_key", "growing_area"}
    keep = [c for c in df.columns if not c.startswith(drop_prefix) and c not in drop]
    return df[keep]


def main() -> None:
    """Score every rule and print the comparison table."""
    chl = pd.read_parquet(CHL_PATH)
    other = non_chl_features()
    summary = []
    for rule in RULES:
        f = labels_and_persistence(chl, rule)
        train_issue = f[f["date"] <= T.TRAIN_END - pd.Timedelta(days=T.HORIZON_DAYS)]
        lifts = rolling_lift(f, other)
        row = {
            "rule": rule.name,
            "labelled_share_train": train_issue["y"].notna().mean(),
            "labelled_share_winter": train_issue.loc[train_issue["month"].isin([6, 7, 8]), "y"]
            .notna()
            .mean(),
            **noise_stats(f),
            "persistence_lift_mean": lifts["persistence_lift"].mean(),
            "model_lift_mean": lifts["model_lift"].mean(),
            "model_lift_min": lifts["model_lift"].min(),
        }
        summary.append(row)
        print(rule.name, lifts.round(2).to_dict(orient="index"), flush=True)
    table = pd.DataFrame(summary).set_index("rule")
    eligible = table[table["labelled_share_train"] >= MIN_LABELLED]
    best = eligible.sort_values(["model_lift_mean", "labelled_share_train"], ascending=False)
    print("\n" + table.round(3).to_string())
    print(f"\nselected by the pre-stated rule: {best.index[0]}")


if __name__ == "__main__":
    main()
