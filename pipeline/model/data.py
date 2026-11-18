"""Model inputs: feature selection, time-ordered splits with purge gaps, and sub-regions.

Splits (brief section 6, refined in D012):
  fit    issue dates <= 2021-12-24       model fitting during tuning
  tune   2022-01-01 .. 2022-12-24        early stopping / hyperparameters
  train  = fit + tune (<= 2022-12-24)    final refit
  val    2023-01-01 .. 2023-12-24        calibration and risk-tier cut-offs
  test   2024-01-01 ..                   scored once, at the end

The target for issue date t uses chl on t+1..t+7, so the last 7 days of each period would
"see" the next period's data. Those rows are purged (the 7-day gaps above).
"""

import numpy as np
import pandas as pd

from pipeline.features.build import OUT_PATH as TABLE_PATH
from pipeline.features.target import HORIZON_DAYS as HORIZON

LABEL = "y_fixed"  # primary label (D011); "y_trailing" is the sensitivity analysis
PERIODS = {
    "fit": ("2016-01-01", "2021-12-31"),
    "tune": ("2022-01-01", "2022-12-31"),
    "train": ("2016-01-01", "2022-12-31"),
    "val": ("2023-01-01", "2023-12-31"),
    "test": ("2024-01-01", "2099-12-31"),
}

# Columns that are identifiers, targets, or same-day chl (not available at issue time t).
NON_FEATURES = {
    "area_id", "date", "split", "match_key", "growing_area", "processing", "region",
    "log_chl", "n_valid",
}  # fmt: skip
TARGET_PREFIXES = ("anomaly_", "fwd_mean_", "fwd_n_", "threshold_", "y_")


def load_table() -> pd.DataFrame:
    """The Phase 2 feature table with a sub-region column added."""
    df = pd.read_parquet(TABLE_PATH)
    df["region"] = df["growing_area"].map(region_of_growing_area())
    return df


def feature_columns(df: pd.DataFrame) -> list[str]:
    """All model features: everything except identifiers, targets and same-day chl.

    The area ID is deliberately NOT a feature, so the model can be applied to areas it has
    never seen (the SA transfer case study). Area-level static features stand in for it.
    """
    return [c for c in df.columns if c not in NON_FEATURES and not c.startswith(TARGET_PREFIXES)]


def period(df: pd.DataFrame, name: str, label: str = LABEL) -> pd.DataFrame:
    """Labelled rows of one period, with the last HORIZON days purged (except for test)."""
    start, end = (pd.Timestamp(x) for x in PERIODS[name])
    if name != "test":
        end = end - pd.Timedelta(days=HORIZON)
    rows = df[(df["date"] >= start) & (df["date"] <= end)]
    return rows[rows[label].notna()]


# Growing-area centroids (EPSG:4326) grouped by coast. Thresholds were chosen from a
# table of centroids so that each group is one contiguous stretch of coast.
def classify_region(lat: float, lon: float) -> str:
    """Tasmanian sub-region for a centroid."""
    if lat > -41.5 and lon < 147.5:
        return "north"  # Port Sorell, Duck Bay, Big Bay, Montagu
    if lon >= 147.9 and lat >= -42.6:
        return "east_coast"  # Triabunna to Moulting Bay
    if lat >= -43.1:
        return "south_east"  # Pitt Water, Norfolk Bay, Tasman Peninsula bays
    return "channel_south"  # D'Entrecasteaux Channel, Bruny Island, far south


def region_of_growing_area() -> dict[str, str]:
    """growing_area -> sub-region, from the theLIST polygons."""
    from pipeline.features.areas import load_tas_areas

    a = load_tas_areas().to_crs(4326)
    c = a.geometry.centroid  # small polygons: degree-based centroid is fine here
    pts = pd.DataFrame({"g": a["growing_area"], "lat": c.y, "lon": c.x})
    mean = pts.groupby("g")[["lat", "lon"]].mean()
    return {g: classify_region(r.lat, r.lon) for g, r in mean.iterrows()}


def week_blocks(dates: pd.Series) -> np.ndarray:
    """Calendar-week block IDs for the block bootstrap (rows in a week are correlated)."""
    return (dates - pd.Timestamp("2016-01-04")).dt.days.to_numpy() // 7
