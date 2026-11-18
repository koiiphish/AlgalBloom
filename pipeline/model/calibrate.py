"""Isotonic calibration stored as plain JSON (breakpoints), so the daily pipeline needs no
pickles and the mapping can be read by a human.

Isotonic regression learns a step-wise increasing map from raw score to probability. It needs
plenty of data (the validation year has ~15,000 labelled rows) and makes no shape assumption,
unlike Platt (logistic) scaling.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from sklearn.isotonic import IsotonicRegression


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
