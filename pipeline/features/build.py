"""Assemble the Tasmanian area x day feature table: target(s), features and quality flags.

Inputs (built by the other modules in this package, all in data/interim/):
  chl_area_day_v202211.parquet  per-area daily chl and valid-pixel counts   (chl.py)
  ocean_area_day.parquet        SST, SST anomaly, MHW, MLD, current speed  (ocean.py)
  weather_area_day.parquet      past weather + fc7_* forecast-window drivers (weather.py)

Run:  uv run python -m pipeline.features.build
Output: data/features/area_day_tas.parquet (git-ignored; rebuildable)
"""

import numpy as np
import pandas as pd

from pipeline.config import DATA_DIR
from pipeline.features import target as T
from pipeline.features.areas import load_tas_areas
from pipeline.features.availability import OCEAN_MODEL_LAG_DAYS, SST_LAG_DAYS
from pipeline.features.chl import OUT_PATH as CHL_PATH
from pipeline.features.chl_features import build_chl_features
from pipeline.features.ocean import OUT_PATH as OCEAN_PATH
from pipeline.features.weather import OUT_PATH as WEATHER_PATH

OUT_PATH = DATA_DIR / "features" / "area_day_tas.parquet"
VAL_START, TEST_START = pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01")
SST_COLS = ["sst", "sst_anom", "mhw_run_days", "mhw"]
MODEL_COLS = ["mld", "current_speed"]


def targets(chl: pd.DataFrame) -> pd.DataFrame:
    """Anomalies and labels under both baselines (fixed = brief; trailing = option C)."""
    base = T.add_log_chl(T.complete_daily_index(chl))
    fixed = T.add_target(T.add_anomaly(base, T.fixed_baseline(base)))
    trailing = T.add_target(T.add_anomaly(base, T.trailing_baseline(base)))
    keep = ["anomaly", "fwd_mean", "fwd_n", "threshold", "y"]
    out = fixed[["area_id", "date", "log_chl", "n_valid", "weight", "processing", *keep]]
    out = out.rename(columns={c: f"{c}_fixed" for c in keep})
    tr = trailing[["area_id", "date", *keep]].rename(columns={c: f"{c}_trailing" for c in keep})
    return out.merge(tr, on=["area_id", "date"], how="left")


def lagged(df: pd.DataFrame, cols: list[str], lag: int) -> pd.DataFrame:
    """Shift columns by `lag` days within each area, so the value at t is from t - lag."""
    out = df[["area_id", "date"]].copy()
    out[cols] = df.sort_values(["area_id", "date"]).groupby("area_id")[cols].shift(lag)
    return out


def split_label(dates: pd.Series) -> pd.Series:
    """Time-ordered split: train <= 2022, validate 2023, test 2024+ (brief section 6)."""
    return pd.Series(
        np.select([dates < VAL_START, dates < TEST_START], ["train", "val"], "test"),
        index=dates.index,
    )


def build() -> pd.DataFrame:
    """Join targets, chl features, lagged ocean features, weather and static features."""
    chl = pd.read_parquet(CHL_PATH)
    tgt = targets(chl)
    # Chl features use the fixed-baseline anomaly (the brief's definition).
    cols = ["area_id", "date", "anomaly", "log_chl", "weight"]
    feats = build_chl_features(tgt.rename(columns={"anomaly_fixed": "anomaly"})[cols])
    ocean = pd.read_parquet(OCEAN_PATH).sort_values(["area_id", "date"])
    sst = lagged(ocean, SST_COLS, SST_LAG_DAYS)
    model = lagged(ocean, MODEL_COLS, OCEAN_MODEL_LAG_DAYS)
    static_ocean = ocean.groupby("area_id")[["sst_cell_km", "model_cell_km"]].first()
    weather = pd.read_parquet(WEATHER_PATH)

    df = (
        tgt.merge(feats, on=["area_id", "date"], how="left")
        .merge(sst, on=["area_id", "date"], how="left")
        .merge(model, on=["area_id", "date"], how="left")
        .merge(weather, on=["area_id", "date"], how="left")
        .merge(static_ocean, on="area_id", how="left")
    )
    areas = load_tas_areas()[["area_id", "match_key", "growing_area", "area_ha"]]
    n_pix = chl.groupby("area_id")["n_pixels"].first().rename("n_pixels")
    df = df.merge(areas, on="area_id", how="left").merge(n_pix, on="area_id", how="left")
    doy = df["date"].dt.day_of_year
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["split"] = split_label(df["date"])
    return df.sort_values(["area_id", "date"]).reset_index(drop=True)


def main() -> None:
    """Build, save and print a short summary per split."""
    df = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(f"wrote {len(df):,} rows x {df.shape[1]} columns -> {OUT_PATH}")
    summary = df.groupby("split").agg(
        rows=("date", "size"),
        labelled_fixed=("y_fixed", lambda s: s.notna().mean()),
        positive_rate_fixed=("y_fixed", "mean"),
        positive_rate_trailing=("y_trailing", "mean"),
    )
    # Never print test label rates during development: they'd invite tuning choices to the test set.
    summary.loc[summary.index == "test", ["positive_rate_fixed", "positive_rate_trailing"]] = np.nan
    print(summary.round(3).to_string())


if __name__ == "__main__":
    main()
