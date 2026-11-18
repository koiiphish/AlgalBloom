"""The shipped forecast: calibrated chlorophyll persistence (D013).

Phase 3 found that weather, SST, ocean-model and seasonal features add no measurable skill
beyond recent chlorophyll for this target (D011 updates, D013). So the forecast is the
simplest method that works:

  score(t) = clear-sky-weighted mean chl anomaly over t-15..t-2 (`chl_anom_wmean14`)
  p(t)     = Platt (logistic) calibration of the score, fitted on the validation year (2023);
             isotonic overfits this weak score (see pipeline.model.calibrate)

If there was no clear view in those 14 days, the area falls back to its training-years
positive rate for that calendar month (the seasonal-climatology baseline), and the output is
flagged `stale_chl` so the map can say so.

Run:  uv run python -m pipeline.model.persistence
Output: models/persistence_tas.json (calibrator, climatology fallback, tier cut-offs)
"""

import json

import numpy as np
import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.model.baselines import climatology, climatology_table
from pipeline.model.calibrate import Calibrator
from pipeline.model.data import LABEL, load_table, period
from pipeline.model.tiers import choose_cutoffs, tier_report

SCORE = "chl_anom_wmean14"
OUT_PATH = REPO_ROOT / "models" / "persistence_tas.json"


def predict(df: pd.DataFrame, cal: Calibrator, clim_table: pd.DataFrame) -> pd.DataFrame:
    """Probability and stale flag for each row."""
    stale = df[SCORE].isna().to_numpy()
    p = cal.predict(df[SCORE].to_numpy())
    p = np.where(stale, climatology(df, clim_table).to_numpy(), p)
    return pd.DataFrame({"p": p, "stale_chl": stale}, index=df.index)


def fit(df: pd.DataFrame, label: str = LABEL) -> tuple[Calibrator, pd.DataFrame]:
    """Calibrator (on validation rows with a score) and the climatology fallback table."""
    val = period(df, "val", label)
    cal = Calibrator.fit_platt(val[SCORE].to_numpy(), val[label].to_numpy())
    return cal, climatology_table(df, label)


def main() -> None:
    """Fit on train/val, choose tier cut-offs on val, save, and print validation numbers."""
    df = load_table()
    cal, clim = fit(df)
    val = period(df, "val")
    pred = predict(val, cal, clim)
    cuts = choose_cutoffs(val[LABEL].to_numpy(), pred["p"].to_numpy())
    report = tier_report(val[LABEL].to_numpy(), pred["p"].to_numpy(), cuts)
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "method": "calibrated chlorophyll persistence (D013)",
                "score": SCORE,
                "label": LABEL,
                "calibrator": {"x": cal.x, "y": cal.y},
                "climatology_fallback": clim.to_dict(orient="records"),
                "tier_cutoffs": cuts,
                "validation_tiers": report.reset_index().to_dict(orient="records"),
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"validation rows {len(val):,}; stale share {pred['stale_chl'].mean():.3f}")
    print("tier cut-offs (probability):", {k: round(v, 3) for k, v in cuts.items()})
    print(report.round(3).to_string())
    print(f"saved {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
