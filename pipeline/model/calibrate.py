"""Probability calibration stored as plain JSON (breakpoints), so the daily pipeline needs no
pickles and the mapping can be read by a human.

Two methods (brief section 6):
  - isotonic: a step-wise increasing map; no shape assumption, but with a weak score it
    overfits the tails (e.g. a jump to p = 1.0 on a handful of rows) and makes few, wide steps
  - Platt: a logistic curve p = 1 / (1 + exp(-(a + b * score))); two parameters, smooth.
    Used for the shipped persistence forecast (D013). Stored as dense breakpoints so both
    methods share one format.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


@dataclass
class Calibrator:
    """Piecewise-linear increasing map from raw score to probability."""

    x: list[float]
    y: list[float]

    @classmethod
    def fit(cls, score: np.ndarray, label: np.ndarray) -> "Calibrator":
        """Fit on rows with a finite score."""
        ok = np.isfinite(score)
        iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
        iso.fit(score[ok], label[ok])
        return cls(x=iso.X_thresholds_.tolist(), y=iso.y_thresholds_.tolist())

    @classmethod
    def fit_platt(cls, score: np.ndarray, label: np.ndarray, n_points: int = 201) -> "Calibrator":
        """Logistic (Platt) calibration on rows with a finite score, as breakpoints."""
        ok = np.isfinite(score)
        lr = LogisticRegression(C=1e6).fit(score[ok].reshape(-1, 1), label[ok])
        lo, hi = np.percentile(score[ok], [0.1, 99.9])
        x = np.linspace(lo, hi, n_points)
        y = lr.predict_proba(x.reshape(-1, 1))[:, 1]
        return cls(x=x.tolist(), y=y.tolist())

    def predict(self, score: np.ndarray) -> np.ndarray:
        """Probability for each score (NaN stays NaN; outside the fitted range is clipped)."""
        out = np.interp(score, self.x, self.y)
        return np.where(np.isfinite(score), out, np.nan)

    def save(self, path: Path) -> None:
        """Write as JSON."""
        path.write_text(json.dumps(asdict(self)), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Calibrator":
        """Read from JSON."""
        return cls(**json.loads(path.read_text(encoding="utf-8")))
