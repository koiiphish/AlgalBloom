"""Map calibrated probability to Low / Moderate / High risk tiers (brief section 6).

Cut-offs are chosen on the validation year only, by a false-alarm budget:
  Moderate: flagged on at most 20% of normal (non-bloom) weeks
  High:     flagged on at most 5% of normal weeks
A false-alarm budget makes the tiers mean the same thing in plain words ("High is rare in a
normal week") regardless of how sharp the probabilities are. Each tier's observed bloom-week
rate on validation is reported next to it.
"""

import numpy as np
import pandas as pd

FAR_MODERATE, FAR_HIGH = 0.20, 0.05
TIERS = ("Low", "Moderate", "High")


def _min_threshold_within_far(y: np.ndarray, p: np.ndarray, far: float) -> float:
    """Smallest probability cut-off that flags at most `far` of the y == 0 rows."""
    neg = np.sort(p[y == 0])
    for th in np.unique(p):
        if (neg >= th).mean() <= far:
            return float(th)
    return float(np.inf)


def choose_cutoffs(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    """Moderate and High probability cut-offs from validation labels and probabilities."""
    moderate = _min_threshold_within_far(y, p, FAR_MODERATE)
    high = _min_threshold_within_far(y, p, FAR_HIGH)
    return {"moderate": moderate, "high": max(high, moderate)}


def assign(p: np.ndarray, cuts: dict[str, float]) -> np.ndarray:
    """Tier name for each probability."""
    return np.select([p >= cuts["high"], p >= cuts["moderate"]], ["High", "Moderate"], "Low")


def tier_report(y: np.ndarray, p: np.ndarray, cuts: dict[str, float]) -> pd.DataFrame:
    """Per tier: share of weeks, observed bloom-week rate, share of all bloom weeks, false-alarm
    rate (share of normal weeks in this tier)."""
    t = assign(p, cuts)
    rows = []
    for name in TIERS:
        m = t == name
        rows.append({
            "tier": name,
            "share_of_weeks": m.mean(),
            "bloom_rate": y[m].mean() if m.any() else np.nan,
            "share_of_bloom_weeks": y[m].sum() / max(y.sum(), 1),
            "share_of_normal_weeks": (m & (y == 0)).sum() / max((y == 0).sum(), 1),
        })  # fmt: skip
    return pd.DataFrame(rows).set_index("tier")
