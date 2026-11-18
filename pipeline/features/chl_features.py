"""Chlorophyll features at issue date t, using only data up to t - CHL_LAG_DAYS.

Input: the anomaly table from pipeline.features.target (one area's complete daily calendar,
columns date, log_chl, anomaly). Cloudy days are NaN; features describe the most recent
*valid* observations and how stale they are, so gaps are explicit rather than hidden.
"""

import numpy as np
import pandas as pd

from pipeline.features.availability import CHL_LAG_DAYS

LOOKBACK_DAYS = 14
N_LAGS = 7  # raw anomaly at t-lag ... t-lag-6 (NaN where cloudy; boosted trees handle NaN)


def _slope_per_day(values: np.ndarray) -> float:
    """Least-squares slope (per day) through the finite values of a daily window."""
    x = np.arange(values.size, dtype=float)
    ok = np.isfinite(values)
    if ok.sum() < 3:
        return np.nan
    return float(np.polyfit(x[ok], values[ok], 1)[0])


def _rising_run(values: np.ndarray) -> int:
    """How many consecutive valid observations (ending at the latest) were each higher than
    the previous valid one, e.g. for 'chlorophyll rising 4 observations running'."""
    v = values[np.isfinite(values)]
    run = 0
    for i in range(v.size - 1, 0, -1):
        if v[i] > v[i - 1]:
            run += 1
        else:
            break
    return run


def area_chl_features(g: pd.DataFrame, lag: int = CHL_LAG_DAYS) -> pd.DataFrame:
    """Features for every issue date of ONE area (g on a complete daily calendar, sorted)."""
    anom = g["anomaly"].to_numpy(dtype=float)
    level = g["log_chl"].to_numpy(dtype=float)
    n = anom.size
    rows = []
    for t in range(n):
        end = t - lag  # last usable index (inclusive)
        start = end - LOOKBACK_DAYS + 1
        if end < 0:
            rows.append({})
            continue
        win = anom[max(start, 0) : end + 1]
        lev = level[max(start, 0) : end + 1]
        valid_idx = np.flatnonzero(np.isfinite(win))
        last = valid_idx[-1] if valid_idx.size else None
        row = {
            "chl_anom_last": win[last] if last is not None else np.nan,
            "chl_level_last": lev[last] if last is not None else np.nan,
            "chl_days_since_obs": (win.size - 1 - last + lag) if last is not None else np.nan,
            "chl_anom_mean7": np.nanmean(win[-7:]) if np.isfinite(win[-7:]).any() else np.nan,
            "chl_anom_mean14": np.nanmean(win) if valid_idx.size else np.nan,
            "chl_anom_max14": np.nanmax(win) if valid_idx.size else np.nan,
            "chl_slope14": _slope_per_day(win),
            "chl_n_valid14": int(valid_idx.size),
            "chl_rising_run": _rising_run(win),
        }
        for k in range(N_LAGS):
            i = end - k
            row[f"chl_anom_lag{lag + k}"] = anom[i] if i >= 0 else np.nan
        rows.append(row)
    out = pd.DataFrame(rows, index=g.index)
    out.insert(0, "date", g["date"].to_numpy())
    out.insert(0, "area_id", g["area_id"].to_numpy())
    return out


def build_chl_features(anoms: pd.DataFrame, lag: int = CHL_LAG_DAYS) -> pd.DataFrame:
    """Chl features for all areas (anoms must be on a complete daily calendar per area)."""
    parts = [
        area_chl_features(g.sort_values("date").reset_index(drop=True), lag)
        for _, g in anoms.groupby("area_id")
    ]
    return pd.concat(parts, ignore_index=True)
