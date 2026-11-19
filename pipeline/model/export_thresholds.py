"""Export the label thresholds used for verification (Phase 6, D016).

The label "elevated" means the clear-sky-weighted mean anomaly over t+1..t+7 exceeds the area's
training-years 90th percentile for the issue month (pipeline.features.target.add_target). The
verification page applies the same rule to issued forecasts, so it needs those thresholds; they
are exported once here (the deployment file models/forecast_tas.json stays frozen).

Run:  uv run python -m pipeline.model.export_thresholds
Output: models/label_thresholds_tas.json
"""

import json

import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.features import target as T
from pipeline.features.chl import OUT_PATH as CHL_PATH
from pipeline.model.deploy import baseline_table

OUT_PATH = REPO_ROOT / "models" / "label_thresholds_tas.json"


def thresholds() -> pd.DataFrame:
    """area_id, month, threshold: exactly as computed when the training labels were built."""
    chl = pd.read_parquet(CHL_PATH)
    base = T.add_log_chl(T.complete_daily_index(chl))
    labelled = T.add_target(T.add_anomaly(base, baseline_table()))
    return (
        labelled[["area_id", "month", "threshold"]]
        .dropna()
        .drop_duplicates(["area_id", "month"])
        .sort_values(["area_id", "month"])
        .reset_index(drop=True)
    )


def main() -> None:
    """Write the thresholds and the label rule they belong to."""
    thr = thresholds()
    out = {
        "label": "y_fixed",
        "rule": "clear-sky-weighted mean log10 anomaly over t+1..t+7 (>= "
        f"{T.MIN_VALID_DAYS} valid days) > threshold for the issue month",
        "quantile": T.QUANTILE,
        "train_end": str(T.TRAIN_END.date()),
        "min_valid_days": T.MIN_VALID_DAYS,
        "thresholds": thr.round(6).to_dict(orient="records"),
    }
    OUT_PATH.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{len(thr)} area-month thresholds -> {OUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
