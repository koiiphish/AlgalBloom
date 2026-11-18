"""Train the LightGBM bloom-week classifier and calibrate it (Phase 3).

Steps (splits in pipeline.model.data):
  1. Small hyperparameter grid: fit on `fit` (<= 2021), early-stop and score PR-AUC on `tune`
     (2022).
  2. Refit the best configuration on `train` (<= 2022) with the early-stopped tree count.
  3. Isotonic calibration of the raw score on `val` (2023).
The test period is never touched here.

Run:  uv run python -m pipeline.model.train [--label y_fixed|y_trailing]
Output: models/lgbm_tas_<label>.txt, models/calibrator_tas_<label>.json,
        models/lgbm_tas_<label>.json (metadata)
"""

import argparse
import itertools
import json
from datetime import UTC, datetime

import lightgbm as lgb
import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.model.calibrate import Calibrator
from pipeline.model.data import LABEL, PERIODS, feature_columns, load_table, period
from pipeline.model.metrics import pr_auc

MODELS_DIR = REPO_ROOT / "models"
BASE_PARAMS = {
    "objective": "binary",
    "learning_rate": 0.03,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "verbosity": -1,
    "seed": 42,
    "deterministic": True,
    "num_threads": 4,
}
GRID = {"num_leaves": [15, 31, 63], "min_child_samples": [100, 400]}
MAX_ROUNDS, EARLY_STOP = 3000, 150


def paths(label: str) -> dict[str, object]:
    """Artefact paths for one label."""
    stem = f"lgbm_tas_{label}"
    return {
        "model": MODELS_DIR / f"{stem}.txt",
        "meta": MODELS_DIR / f"{stem}.json",
        "calibrator": MODELS_DIR / f"calibrator_tas_{label}.json",
    }


def tune(df: pd.DataFrame, feats: list[str], label: str) -> tuple[dict, int, list[dict]]:
    """Grid search on fit -> tune. Returns best params, best tree count and the full log."""
    fit, tun = period(df, "fit", label), period(df, "tune", label)
    dfit = lgb.Dataset(fit[feats], fit[label], free_raw_data=False)
    dtun = lgb.Dataset(tun[feats], tun[label], reference=dfit, free_raw_data=False)
    log = []
    for values in itertools.product(*GRID.values()):
        params = {
            **BASE_PARAMS,
            **dict(zip(GRID, values, strict=True)),
            "metric": "average_precision",
        }
        booster = lgb.train(
            params, dfit, MAX_ROUNDS, valid_sets=[dtun],
            callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)],
        )  # fmt: skip
        score = pr_auc(
            tun[label].to_numpy(), booster.predict(tun[feats], num_iteration=booster.best_iteration)
        )
        log.append(
            {
                **dict(zip(GRID, values, strict=True)),
                "best_iter": booster.best_iteration,
                "tune_pr_auc": score,
            }
        )
        print(f"  {log[-1]}", flush=True)
    best = max(log, key=lambda r: r["tune_pr_auc"])
    params = {**BASE_PARAMS, **{k: best[k] for k in GRID}}
    return params, int(best["best_iter"]), log


def main() -> None:
    """Tune, refit, calibrate and save."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default=LABEL, choices=["y_fixed", "y_trailing"])
    label = parser.parse_args().label

    df = load_table()
    feats = feature_columns(df)
    print(f"{len(feats)} features; label {label}", flush=True)
    params, n_trees, log = tune(df, feats, label)

    train, val = period(df, "train", label), period(df, "val", label)
    # The full training set is ~1/6 larger than `fit`, so scale the tree count to match.
    n_final = int(round(n_trees * len(train) / len(period(df, "fit", label))))
    booster = lgb.train(params, lgb.Dataset(train[feats], train[label]), n_final)
    raw_val = booster.predict(val[feats])
    cal = Calibrator.fit(raw_val, val[label].to_numpy())

    p = paths(label)
    MODELS_DIR.mkdir(exist_ok=True)
    booster.save_model(p["model"])
    cal.save(p["calibrator"])
    meta = {
        "label": label,
        "trained_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "features": feats,
        "params": params,
        "n_trees": n_final,
        "tuning_log": log,
        "periods": PERIODS,
        "rows": {"train": len(train), "val": len(val)},
        "val_pr_auc_raw": pr_auc(val[label].to_numpy(), raw_val),
        "val_positive_rate": float(val[label].mean()),
        "chl_source": "OLCI 300 m L3, Copernicus version 202211 (D006)",
    }
    p["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"best {params['num_leaves']} leaves / {params['min_child_samples']} min child; "
          f"{n_final} trees; val PR-AUC (raw) {meta['val_pr_auc_raw']:.3f} "
          f"vs positive rate {meta['val_positive_rate']:.3f}")  # fmt: skip
    print("saved:", ", ".join(str(v.relative_to(REPO_ROOT)) for v in p.values()))


if __name__ == "__main__":
    main()
