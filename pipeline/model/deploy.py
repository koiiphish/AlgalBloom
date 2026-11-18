"""Build the frozen deployment file for the daily forecast (Phase 4, D014).

Everything the daily job needs is in one small JSON, so it never touches the 2 GB history:
  baseline      each area's 2016-2022 median log10 chl per calendar month (the fixed baseline
                the label and the score are defined against; D011)
  calibrator    Platt calibration of the persistence score, REFIT on 2023-01 .. 2026-10
                (validation + test years; decision B in D014). The Phase 3 test evaluation used
                the 2023-only calibration and stays as reported in the model card.
  tier_cutoffs  Moderate / High cut-offs, re-chosen on the same window with the same
                false-alarm budgets (20% / 5% of normal weeks; pipeline.model.tiers)
  climatology_fallback  training-years bloom-week rate per area x month, used when an area
                had no clear view in the 14-day score window (`stale_chl`)

Run:  uv run python -m pipeline.model.deploy
Output: models/forecast_tas.json
"""

import json
import subprocess
from datetime import UTC, datetime

import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.features import target as T
from pipeline.features.chl import OUT_PATH as CHL_PATH
from pipeline.model.baselines import climatology_table
from pipeline.model.calibrate import Calibrator
from pipeline.model.data import LABEL, load_table
from pipeline.model.persistence import SCORE, predict
from pipeline.model.tiers import FAR_HIGH, FAR_MODERATE, choose_cutoffs, tier_report

OUT_PATH = REPO_ROOT / "models" / "forecast_tas.json"
FIT_START, FIT_END = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-10-31")
MODEL_VERSION = "persistence-1.1"  # 1.0 = Phase 3 (2023 calibration); 1.1 = refit (D014)


def baseline_table() -> pd.DataFrame:
    """The fixed 2016-2022 baseline, built exactly as in the feature pipeline."""
    chl = pd.read_parquet(CHL_PATH)
    base = T.add_log_chl(T.complete_daily_index(chl))
    return T.fixed_baseline(base)


def fit_window(df: pd.DataFrame) -> pd.DataFrame:
    """Labelled rows of the recalibration window."""
    rows = df[(df["date"] >= FIT_START) & (df["date"] <= FIT_END)]
    return rows[rows[LABEL].notna()]


def build() -> dict:
    """Fit everything and return the deployment dictionary."""
    df = load_table()
    win = fit_window(df)
    cal = Calibrator.fit_platt(win[SCORE].to_numpy(), win[LABEL].to_numpy())
    clim = climatology_table(df)
    p = predict(win, cal, clim)["p"].to_numpy()
    y = win[LABEL].to_numpy()
    cuts = choose_cutoffs(y, p)
    base = baseline_table()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=REPO_ROOT).stdout.strip()  # fmt: skip
    return {
        "model_version": MODEL_VERSION,
        "method": "calibrated chlorophyll persistence (D013), recalibrated (D014)",
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_commit": commit,
        "score": SCORE,
        "label": LABEL,
        "fit_window": [str(FIT_START.date()), str(FIT_END.date())],
        "fit_rows": int(len(win)),
        "fit_positive_rate": round(float(y.mean()), 4),
        "far_budgets": {"moderate": FAR_MODERATE, "high": FAR_HIGH},
        "min_valid_pixels": T.MIN_VALID_PIXELS,
        "calibrator": {"x": [round(v, 6) for v in cal.x], "y": [round(v, 6) for v in cal.y]},
        "tier_cutoffs": {k: round(v, 6) for k, v in cuts.items()},
        "fit_window_tiers": tier_report(y, p, cuts).round(4).reset_index().to_dict("records"),
        "baseline": base.dropna().round(6).to_dict(orient="records"),
        "climatology_fallback": clim.round(6).to_dict(orient="records"),
    }


def main() -> None:
    """Build, save and print the new calibration next to the Phase 3 one."""
    out = build()
    OUT_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    old = json.loads((REPO_ROOT / "models" / "persistence_tas.json").read_text())
    print(f"fit rows {out['fit_rows']:,}, positive rate {out['fit_positive_rate']}")
    print("tier cut-offs  Phase 3:", {k: round(v, 3) for k, v in old["tier_cutoffs"].items()},
          " deployed:", {k: round(v, 3) for k, v in out["tier_cutoffs"].items()})  # fmt: skip
    old_cal = Calibrator(**old["calibrator"])
    new_cal = Calibrator(**out["calibrator"])
    for s in (-0.3, 0.0, 0.2, 0.4, 0.6):
        print(f"score {s:+.1f}: p {old_cal.predict([s])[0]:.3f} -> {new_cal.predict([s])[0]:.3f}")
    print(pd.DataFrame(out["fit_window_tiers"]).to_string(index=False))
    print(f"baseline rows {len(out['baseline'])}; saved {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
