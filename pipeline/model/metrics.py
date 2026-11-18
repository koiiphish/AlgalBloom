"""Evaluation metrics (brief section 6): PR-AUC, Brier score, reliability, recall at a fixed
false-alarm rate, with confidence intervals from a block bootstrap over calendar weeks.

Rows from the same week are strongly correlated (one weather event affects many areas and
consecutive issue dates), so resampling single rows would give over-confident intervals.
"""

from collections.abc import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_curve

FAR = 0.10  # fixed false-alarm rate (false-positive rate) for the recall metric


def pr_auc(y: np.ndarray, p: np.ndarray) -> float:
    """Area under the precision-recall curve (average precision). Random = positive rate."""
    return float(average_precision_score(y, p))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    """Mean squared error of the probability. Lower is better."""
    return float(brier_score_loss(y, p))


def recall_at_far(y: np.ndarray, p: np.ndarray, far: float = FAR) -> float:
    """Share of bloom weeks caught when only `far` of normal weeks are flagged."""
    fpr, tpr, _ = roc_curve(y, p)
    return float(tpr[fpr <= far].max())


METRICS: dict[str, Callable[[np.ndarray, np.ndarray], float]] = {
    "pr_auc": pr_auc,
    "brier": brier,
    "recall_at_far10": recall_at_far,
}


def reliability(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Mean forecast vs observed frequency in equal-count bins of the probability."""
    df = pd.DataFrame({"y": y, "p": p})
    df["bin"] = pd.qcut(df["p"].rank(method="first"), bins, labels=False)
    return df.groupby("bin").agg(p_mean=("p", "mean"), y_rate=("y", "mean"), n=("y", "size"))


def block_bootstrap(
    y: np.ndarray, p: np.ndarray, blocks: np.ndarray, fn: Callable, n_boot: int = 300,
    seed: int = 0,
) -> tuple[float, float]:  # fmt: skip
    """95% interval of fn(y, p) when whole blocks (weeks) are resampled with replacement."""
    rng = np.random.default_rng(seed)
    uniq, inverse = np.unique(blocks, return_inverse=True)
    members = [np.flatnonzero(inverse == i) for i in range(len(uniq))]
    stats = []
    for _ in range(n_boot):
        idx = np.concatenate([members[i] for i in rng.integers(0, len(uniq), len(uniq))])
        if y[idx].min() == y[idx].max():
            continue  # a resample with only one class has no PR-AUC
        stats.append(fn(y[idx], p[idx]))
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def score_table(
    y: np.ndarray, probs: dict[str, np.ndarray], blocks: np.ndarray, n_boot: int = 300
) -> pd.DataFrame:
    """One row per method: each metric with its bootstrap interval."""
    rows = []
    for name, p in probs.items():
        row = {"method": name, "n": len(y), "positives": int(y.sum())}
        for m, fn in METRICS.items():
            row[m] = fn(y, p)
            row[f"{m}_lo"], row[f"{m}_hi"] = block_bootstrap(y, p, blocks, fn, n_boot)
        rows.append(row)
    return pd.DataFrame(rows).set_index("method")
