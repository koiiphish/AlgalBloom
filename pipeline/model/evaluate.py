"""Final, one-off evaluation on the test period (2024+) for Tasmania (Phase 3, brief section 6).

Everything is frozen before this runs (D013): the label (clear-sky-weighted, fixed baseline),
the shipped method (calibrated persistence), the calibration (Platt, fitted on 2023) and the
tier cut-offs (chosen on 2023). Every comparison method is calibrated the same way on 2023.

Methods:
  persistence   shipped forecast (pipeline.model.persistence)
  climatology   baseline 2: training-years positive rate per area x month
  bgc           baseline 3: Copernicus BGC model forward-window anomaly ("perfect forecast",
                which flatters it; D012)
  lightgbm      documented comparison (not shipped). Its forecast-window weather uses
                OBSERVED weather in the test period too, so it is an optimistic upper bound.

Metrics: PR-AUC, Brier score, recall at a 10% false-alarm rate, with week-block bootstrap 95%
intervals, overall and per sub-region; reliability tables; tier performance. The headline
comparison uses rows where every method has a score (the BGC hindcast ends 2026-09-30).
A sensitivity analysis repeats persistence with the trailing-baseline label (y_trailing).

Run once:  uv run python -m pipeline.model.evaluate
Output:    models/evaluation_tas.json, docs/img/phase3_reliability_tas.png
"""

import json
import subprocess
from datetime import UTC, datetime

import lightgbm as lgb
import matplotlib.pyplot as plt
import pandas as pd

from pipeline.config import REPO_ROOT
from pipeline.model import persistence as P
from pipeline.model.baselines import climatology, climatology_table
from pipeline.model.calibrate import Calibrator
from pipeline.model.data import LABEL, load_table, period, week_blocks
from pipeline.model.metrics import reliability, score_table
from pipeline.model.tiers import tier_report

OUT_JSON = REPO_ROOT / "models" / "evaluation_tas.json"
OUT_FIG = REPO_ROOT / "docs" / "img" / "phase3_reliability_tas.png"
BGC_PATH = REPO_ROOT / "data" / "interim" / "bgc_area_day.parquet"
METHODS = ("persistence", "climatology", "bgc", "lightgbm")


def raw_scores(df: pd.DataFrame, rows: pd.DataFrame, clim: pd.DataFrame) -> pd.DataFrame:
    """Uncalibrated score of every method for the given rows."""
    meta = json.loads((REPO_ROOT / "models" / f"lgbm_tas_{LABEL}.json").read_text())
    booster = lgb.Booster(model_file=str(REPO_ROOT / "models" / f"lgbm_tas_{LABEL}.txt"))
    return pd.DataFrame(
        {
            "persistence": rows[P.SCORE],  # NaN -> climatology fallback after calibration
            "climatology": climatology(rows, clim),
            "bgc": rows["bgc_fwd_anom"],
            "lightgbm": booster.predict(rows[meta["features"]]),
        },
        index=rows.index,
    )


def calibrated(
    val: pd.DataFrame, test: pd.DataFrame, s_val: pd.DataFrame, s_test: pd.DataFrame,
    clim: pd.DataFrame, label: str,
) -> pd.DataFrame:  # fmt: skip
    """Platt-calibrate every method on validation, apply to test (persistence via its module)."""
    out = pd.DataFrame(index=test.index)
    for m in METHODS:
        if m == "persistence":
            cal = Calibrator.fit_platt(val[P.SCORE].to_numpy(), val[label].to_numpy())
            out[m] = P.predict(test, cal, clim)["p"]
        elif m == "climatology":
            out[m] = s_test[m]  # already a probability (training-years rate)
        else:
            cal = Calibrator.fit_platt(s_val[m].to_numpy(), val[label].to_numpy())
            out[m] = cal.predict(s_test[m].to_numpy())
    return out


def evaluate(df: pd.DataFrame, label: str = LABEL) -> dict:
    """All metrics for one label."""
    val, test = period(df, "val", label), period(df, "test", label)
    clim = climatology_table(df, label)
    probs = calibrated(
        val, test, raw_scores(df, val, clim), raw_scores(df, test, clim), clim, label
    )
    common = probs.notna().all(axis=1)
    t, p = test[common], probs[common]
    y, blocks = t[label].to_numpy(), week_blocks(t["date"])
    result = {
        "label": label,
        "rows_test": int(len(test)),
        "rows_common": int(common.sum()),
        "common_period": [str(t["date"].min().date()), str(t["date"].max().date())],
        "positive_rate": float(y.mean()),
        "overall": score_table(y, {m: p[m].to_numpy() for m in METHODS}, blocks).to_dict(
            orient="index"
        ),
        "by_region": {},
    }
    # Per test year (reporting only: 2026 contains a prolonged event that inflates the pooled
    # number; nothing is tuned on these results).
    result["by_year"] = {}
    for year, g in t.groupby(t["date"].dt.year):
        gy = g[label].to_numpy()
        tab = score_table(
            gy, {m: p.loc[g.index, m].to_numpy() for m in METHODS}, week_blocks(g["date"])
        )
        result["by_year"][int(year)] = {
            "positive_rate": float(gy.mean()),
            **tab.to_dict(orient="index"),
        }
    for region, g in t.groupby("region"):
        gy = g[label].to_numpy()
        tab = score_table(gy, {m: p.loc[g.index, m].to_numpy() for m in METHODS},
                          week_blocks(g["date"]))  # fmt: skip
        result["by_region"][region] = tab.to_dict(orient="index")
    # Shipped persistence on ALL test rows (not just those with BGC), with its tiers.
    cuts = json.loads(P.OUT_PATH.read_text())["tier_cutoffs"]
    pa, ya = probs["persistence"].to_numpy(), test[label].to_numpy()
    result["persistence_all_rows"] = score_table(
        ya, {"persistence": pa}, week_blocks(test["date"])
    ).to_dict(orient="index")
    result["persistence_tiers"] = tier_report(ya, pa, cuts).to_dict(orient="index")
    result["reliability"] = {
        m: reliability(y, p[m].to_numpy()).to_dict(orient="list") for m in METHODS
    }
    return result


def plot_reliability(res: dict) -> None:
    """Reliability diagram (calibrated probability vs observed bloom-week rate)."""
    colors = {
        "persistence": "#2a78d6",
        "climatology": "#52514e",
        "bgc": "#1baf7a",
        "lightgbm": "#eb6834",
    }
    fig, ax = plt.subplots(figsize=(4.8, 4.4), dpi=120)
    top = 0
    for m, r in res["reliability"].items():
        ax.plot(r["p_mean"], r["y_rate"], marker="o", ms=4, lw=2, color=colors[m], label=m)
        top = max(top, max(r["p_mean"]), max(r["y_rate"]))
    ax.plot([0, top], [0, top], color="#999", lw=1, ls="--", label="perfect")
    ax.set_xlabel("forecast probability (decile mean)")
    ax.set_ylabel("observed bloom-week rate")
    ax.set_title("Reliability, Tasmania test period")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG)


def main() -> None:
    """Run the one-off test evaluation and save the results."""
    df = load_table()
    bgc = pd.read_parquet(BGC_PATH)[["area_id", "date", "bgc_fwd_anom"]]
    df = df.merge(bgc, on=["area_id", "date"], how="left")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT
    ).stdout.strip()
    res = {
        "run_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "code_commit": commit,
        "primary": evaluate(df, LABEL),
        "sensitivity_trailing": evaluate(df, "y_trailing"),
    }
    OUT_JSON.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    plot_reliability(res["primary"])
    ov = pd.DataFrame(res["primary"]["overall"]).T
    print(
        f"test rows {res['primary']['rows_test']:,}; common rows {res['primary']['rows_common']:,}"
        f" ({res['primary']['common_period']}); positive rate {res['primary']['positive_rate']:.3f}"
    )
    print(ov[["pr_auc", "pr_auc_lo", "pr_auc_hi", "brier", "recall_at_far10"]].round(3).to_string())
    for year, tab in res["primary"]["by_year"].items():
        print(
            year,
            f"base {tab['positive_rate']:.3f}",
            {m: round(tab[m]["pr_auc"], 3) for m in METHODS},
        )
    for region, tab in res["primary"]["by_region"].items():
        print(region, {m: round(v["pr_auc"], 3) for m, v in tab.items()})
    print("persistence tiers on test:")
    print(pd.DataFrame(res["primary"]["persistence_tiers"]).T.round(3).to_string())
    print(
        "trailing-label sensitivity:",
        {m: round(v["pr_auc"], 3) for m, v in res["sensitivity_trailing"]["overall"].items()},
    )
    print(f"saved {OUT_JSON.relative_to(REPO_ROOT)}, {OUT_FIG.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
