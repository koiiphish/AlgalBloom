"""The three baselines the model must beat (brief section 6), as raw scores.

Each baseline produces a score where higher = more likely a bloom week. For a fair comparison,
every score (baselines and the model) is turned into a probability the same way: isotonic
calibration fitted on the validation year (`pipeline.model.calibrate`).

1. Persistence: the latest chlorophyll anomaly available at t (from t-2 or earlier, up to 14
   days old). If there is none, use 0 (normal conditions).
2. Seasonal climatology: the training-years positive rate for that area and calendar month.
3. Copernicus BGC model: the model's forward-window chl anomaly (`pipeline.features.bgc`),
   a perfect-forecast version (D012). Missing where no model cell lies within 50 km.
"""

import pandas as pd

from pipeline.model.data import LABEL, period

BASELINES = ("persistence", "climatology", "bgc")


def persistence(df: pd.DataFrame) -> pd.Series:
    """Latest available anomaly (t-2 or earlier); 0 where there's none in the last 14 days."""
    return df["chl_anom_last"].fillna(0.0)


def climatology_table(df: pd.DataFrame, label: str = LABEL) -> pd.DataFrame:
    """Training-years positive rate per area x calendar month."""
    tr = period(df, "train", label)
    return (
        tr.assign(month=tr["date"].dt.month)
        .groupby(["area_id", "month"])[label]
        .mean()
        .rename("clim_rate")
        .reset_index()
    )


def climatology(df: pd.DataFrame, table: pd.DataFrame) -> pd.Series:
    """Look up each row's training-years positive rate (overall training rate if unseen)."""
    keyed = df[["area_id"]].assign(month=df["date"].dt.month)
    out = keyed.merge(table, on=["area_id", "month"], how="left")["clim_rate"]
    out.index = df.index
    return out.fillna(table["clim_rate"].mean())


def bgc(df: pd.DataFrame) -> pd.Series:
    """BGC forward-window anomaly (needs the bgc_fwd_anom column joined in)."""
    return df["bgc_fwd_anom"]


def all_scores(df: pd.DataFrame, clim_table: pd.DataFrame) -> pd.DataFrame:
    """Raw scores of every baseline for the given rows."""
    return pd.DataFrame(
        {
            "persistence": persistence(df),
            "climatology": climatology(df, clim_table),
            "bgc": bgc(df),
        },
        index=df.index,
    )
