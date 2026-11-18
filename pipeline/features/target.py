"""Chlorophyll anomaly and the 7-day-ahead target (see docs/target_definition.md).

Steps, per area:
  1. log_chl   = log10(daily median chl), only on days with >= MIN_VALID_PIXELS valid pixels;
                 weight = that day's clear-sky fraction (valid pixels / area pixels)
  2. baseline  = "normal" log_chl for that area and calendar month, either
                 - fixed:    median over the TRAINING years only (brief's definition), or
                 - trailing: median over the 3 previous calendar years (drift-resistant;
                             option C, under evaluation; see docs/decisions.md D006 update)
  3. anomaly   = log_chl - baseline
  4. fwd_mean  = clear-sky-weighted mean anomaly over days t+1..t+7 (needs >= MIN_VALID_DAYS
                 valid days). Partly cloudy days are noisy, so they count less (D013).
  5. threshold = 90th percentile of fwd_mean for that area and month, TRAINING years only
  6. y         = 1 if fwd_mean > threshold, 0 if not, missing if too few valid days

Every function works on a long table with columns [area_id, date, ...].
"""

import numpy as np
import pandas as pd

MIN_VALID_PIXELS = 5  # kept; partly cloudy days are down-weighted instead (D013)
MIN_VALID_DAYS = 2  # of the 7 days in the forward window
HORIZON_DAYS = 7
QUANTILE = 0.90
TRAIN_END = pd.Timestamp("2022-12-31")  # train <= 2022, validate 2023, test 2024+
TRAILING_YEARS = 3
MIN_CLIM_OBS = 10  # fewer valid days than this in an area-month -> no baseline


def complete_daily_index(df: pd.DataFrame) -> pd.DataFrame:
    """Reindex every area to a gap-free daily calendar (missing days become NaN rows).

    Needed so that "t+1..t+7" means calendar days, not "the next 7 rows".
    """
    full = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    idx = pd.MultiIndex.from_product([sorted(df["area_id"].unique()), full],
                                     names=["area_id", "date"])  # fmt: skip
    return df.set_index(["area_id", "date"]).reindex(idx).reset_index()


def add_log_chl(df: pd.DataFrame, min_valid_pixels: int = MIN_VALID_PIXELS) -> pd.DataFrame:
    """Add log10 chl, masked to NaN where too few pixels were cloud-free, and (when the
    area's pixel count is known) the day's weight = clear-sky fraction, 0 when masked."""
    out = df.copy()
    ok = (out["n_valid"] >= min_valid_pixels) & (out["chl"] > 0)
    out["log_chl"] = np.where(ok, np.log10(out["chl"].where(ok)), np.nan)
    if "n_pixels" in out.columns:
        out["weight"] = np.where(ok, out["n_valid"] / out["n_pixels"], 0.0)
    return out


def fixed_baseline(df: pd.DataFrame, train_end: pd.Timestamp = TRAIN_END) -> pd.DataFrame:
    """Median log_chl per (area, calendar month) using training-period days only."""
    train = df[df["date"] <= train_end]
    g = train.groupby(["area_id", train["date"].dt.month.rename("month")])["log_chl"]
    clim = g.median().where(g.count() >= MIN_CLIM_OBS)
    return clim.rename("baseline").reset_index()


def trailing_baseline(df: pd.DataFrame, years: int = TRAILING_YEARS) -> pd.DataFrame:
    """Median log_chl per (area, month, year) from the same month in the previous `years` years.

    Uses only earlier calendar years, so it never sees the issue date or anything after it.
    """
    d = df.assign(year=df["date"].dt.year, month=df["date"].dt.month)
    rows = []
    for (area, month), g in d.groupby(["area_id", "month"]):
        for year in range(d["year"].min(), d["year"].max() + 1):
            past = g[(g["year"] >= year - years) & (g["year"] < year)]["log_chl"].dropna()
            value = past.median() if len(past) >= MIN_CLIM_OBS else np.nan
            rows.append((area, month, year, value))
    return pd.DataFrame(rows, columns=["area_id", "month", "year", "baseline"])


def add_anomaly(df: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    """Join a baseline table (fixed or trailing) and compute anomaly = log_chl - baseline."""
    out = df.assign(month=df["date"].dt.month)
    keys = ["area_id", "month"] + (["year"] if "year" in baseline.columns else [])
    if "year" in keys:
        out["year"] = out["date"].dt.year
    out = out.merge(baseline, on=keys, how="left")
    out["anomaly"] = out["log_chl"] - out["baseline"]
    return out.drop(columns=[c for c in ("year",) if c in out.columns])


def forward_window(
    s: pd.Series, horizon: int = HORIZON_DAYS, weights: pd.Series | None = None
) -> tuple[pd.Series, pd.Series]:
    """Mean and count of valid values over the NEXT `horizon` days (t+1..t+horizon).

    `s` must be one area's daily series on a complete calendar. Day t itself is excluded.
    How: x = s shifted by one day (x[t] = s[t+1]); a rolling window over the REVERSED x then
    covers x[t..t+horizon-1] = s[t+1..t+horizon]. (A plain trailing window on a forward
    shift truncates at the start of the series; a unit test caught that.)
    With `weights`, the mean is weighted (count stays the number of valid days).
    """
    x = s.shift(-1)[::-1]
    count = x.rolling(horizon, min_periods=1).count()[::-1]
    if weights is None:
        return x.rolling(horizon, min_periods=1).mean()[::-1], count
    w = weights.where(s.notna(), 0.0).shift(-1)[::-1].fillna(0.0)
    num = (x.fillna(0.0) * w).rolling(horizon, min_periods=1).sum()[::-1]
    den = w.rolling(horizon, min_periods=1).sum()[::-1]
    return num / den.where(den > 0), count


def add_target(
    df: pd.DataFrame,
    min_valid_days: int = MIN_VALID_DAYS,
    quantile: float = QUANTILE,
    train_end: pd.Timestamp = TRAIN_END,
) -> pd.DataFrame:
    """Add fwd_mean, fwd_n, threshold and y (1/0/NaN) to an anomaly table."""
    out = df.sort_values(["area_id", "date"]).copy()
    means, counts = [], []
    for _, g in out.groupby("area_id", sort=False):
        m, c = forward_window(g["anomaly"], weights=g["weight"] if "weight" in g else None)
        means.append(m)
        counts.append(c)
    out["fwd_mean"] = pd.concat(means)
    out["fwd_n"] = pd.concat(counts)
    out.loc[out["fwd_n"] < min_valid_days, "fwd_mean"] = np.nan

    # Threshold from training issue dates whose whole window is inside the training period.
    last_train_issue = train_end - pd.Timedelta(days=HORIZON_DAYS)
    train = out[out["date"] <= last_train_issue]
    thr = (
        train.groupby(["area_id", train["date"].dt.month.rename("month")])["fwd_mean"]
        .quantile(quantile)
        .rename("threshold")
        .reset_index()
    )
    out = out.drop(columns=["threshold"], errors="ignore").merge(
        thr, on=["area_id", "month"], how="left"
    )
    labelled = out["fwd_mean"].notna() & out["threshold"].notna()
    out["y"] = np.where(labelled, (out["fwd_mean"] > out["threshold"]).astype(float), np.nan)
    return out
