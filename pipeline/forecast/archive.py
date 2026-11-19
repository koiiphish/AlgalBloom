"""The forecast archive, committed to main by the daily job (decision E, D014).

The near-real-time satellite product keeps only ~18 days, so anything we want later (forecast
verification, rolling recalibration, retraining on archived forecasts) must be saved as we go.

  archive/chl_area_day.csv   per-area daily chl stats. The NRT product revises recent days, so
                             this is "latest value wins" per (area_id, date), with the source
                             and retrieval time of the kept value.
  archive/forecasts.csv      one row per (issue_date, area_id): what was actually published.
                             A same-day re-run replaces that day's rows; earlier days are never
                             changed.

Seed (run once, locally): the last SEED_DAYS of the multi-year history (source my_202211), so the
time series and the 14-day score window work from the first run.
Run:  uv run python -m pipeline.forecast.archive --seed
"""

import argparse

import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.features.chl import OUT_PATH as HISTORY_CHL_PATH

ARCHIVE_DIR = REPO_ROOT / "archive"
CHL_PATH = ARCHIVE_DIR / "chl_area_day.csv"
FORECAST_PATH = ARCHIVE_DIR / "forecasts.csv"
CHL_COLS = ["area_id", "date", "chl", "n_valid", "n_pixels", "chl_core", "n_core", "source",
            "retrieved_utc"]  # fmt: skip
FORECAST_COLS = ["issue_date", "area_id", "model_version", "score", "p", "tier", "stale_chl",
                 "data_latest_date", "run_utc"]  # fmt: skip
SEED_DAYS = 120


def load_chl() -> pd.DataFrame:
    """The chl archive (empty frame with the right columns if it doesn't exist yet)."""
    if not CHL_PATH.exists():
        return pd.DataFrame(columns=CHL_COLS).astype({"date": "datetime64[ns]"})
    return pd.read_csv(CHL_PATH, parse_dates=["date"])


def upsert_chl(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Merge new stats into the archive; for a repeated (area_id, date) the new row wins."""
    both = pd.concat([old[CHL_COLS], new[CHL_COLS]], ignore_index=True)
    both = both.drop_duplicates(["area_id", "date"], keep="last")
    return both.sort_values(["date", "area_id"]).reset_index(drop=True)


def upsert_forecasts(old: pd.DataFrame, today: pd.DataFrame) -> pd.DataFrame:
    """Append today's forecasts, replacing any earlier run for the same issue date."""
    issue = today["issue_date"].iloc[0]
    kept = old[old["issue_date"] != issue] if len(old) else old
    out = pd.concat([kept, today[FORECAST_COLS]], ignore_index=True)
    return out.sort_values(["issue_date", "area_id"]).reset_index(drop=True)


def load_forecasts() -> pd.DataFrame:
    """The issued-forecast archive (empty if none yet)."""
    if not FORECAST_PATH.exists():
        return pd.DataFrame(columns=FORECAST_COLS)
    return pd.read_csv(FORECAST_PATH, dtype={"issue_date": str})


def save(chl: pd.DataFrame, forecasts: pd.DataFrame) -> None:
    """Write both archive files (compact numbers, ISO dates)."""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    num = ["chl", "chl_core"]  # float32 from the extraction; float64 so float_format applies
    chl = chl.astype({c: "float64" for c in num})
    chl.assign(date=chl["date"].dt.strftime("%Y-%m-%d")).to_csv(
        CHL_PATH, index=False, float_format="%.5g"
    )
    # Appending to an empty archive leaves object columns, which ignore float_format.
    forecasts = forecasts.astype({"score": "float64", "p": "float64"})
    forecasts.to_csv(FORECAST_PATH, index=False, float_format="%.5g")


def seed() -> None:
    """Start the chl archive from the last SEED_DAYS of the multi-year history."""
    if CHL_PATH.exists():
        raise SystemExit(f"{CHL_PATH} already exists; not overwriting the archive")
    hist = pd.read_parquet(HISTORY_CHL_PATH)
    hist = hist[hist["date"] > hist["date"].max() - pd.Timedelta(days=SEED_DAYS)].copy()
    hist["source"] = "my_202211"
    hist["retrieved_utc"] = "2026-11-17"  # when the history files were downloaded
    save(upsert_chl(load_chl(), hist), load_forecasts())
    print(f"seeded {len(hist):,} rows ({hist.date.min().date()} .. {hist.date.max().date()})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    if parser.parse_args().seed:
        seed()
