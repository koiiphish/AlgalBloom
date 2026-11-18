"""Tests for the anomaly, baseline and 7-day-ahead target logic (pipeline.features.target)."""

import numpy as np
import pandas as pd
import pytest

from pipeline.features import target as T


def _series(values: list[float], start: str = "2020-01-01", area: str = "a") -> pd.DataFrame:
    dates = pd.date_range(start, periods=len(values), freq="D")
    return pd.DataFrame({"area_id": area, "date": dates, "anomaly": values})


def test_forward_window_uses_exactly_t_plus_1_to_t_plus_7() -> None:
    s = pd.Series(np.arange(20, dtype=float))  # value == day index
    mean, count = T.forward_window(s, horizon=7)
    assert mean[0] == pytest.approx(np.mean(range(1, 8)))  # days 1..7, not 0..6
    assert count[0] == 7
    assert np.isnan(mean[19])  # nothing after the last day


def test_forward_window_ignores_day_t_and_day_t_plus_8() -> None:
    base = pd.Series(np.zeros(20))
    changed = base.copy()
    changed[0] = 100.0  # day t
    changed[8] = 100.0  # day t+8
    assert T.forward_window(changed)[0][0] == T.forward_window(base)[0][0]


def test_add_log_chl_masks_cloudy_days() -> None:
    df = pd.DataFrame({"chl": [1.0, 10.0, 5.0, -999.0], "n_valid": [10, 10, 2, 10]})
    out = T.add_log_chl(df, min_valid_pixels=5)
    assert out["log_chl"].tolist()[:2] == [0.0, 1.0]
    assert np.isnan(out["log_chl"][2])  # too few pixels
    assert np.isnan(out["log_chl"][3])  # fill value


def test_fixed_baseline_uses_training_years_only() -> None:
    dates = pd.date_range("2022-01-01", "2023-01-31", freq="D")
    df = pd.DataFrame({"area_id": "a", "date": dates, "log_chl": 0.0})
    df.loc[df["date"] >= "2023-01-01", "log_chl"] = 99.0  # validation-year data
    clim = T.fixed_baseline(df, train_end=pd.Timestamp("2022-12-31"))
    assert clim.loc[clim["month"] == 1, "baseline"].item() == 0.0  # 2023 not used


def test_trailing_baseline_uses_only_previous_years() -> None:
    dates = pd.date_range("2018-01-01", "2021-12-31", freq="D")
    df = pd.DataFrame({"area_id": "a", "date": dates, "log_chl": dates.year - 2018.0})
    b = T.trailing_baseline(df, years=3).set_index(["month", "year"])["baseline"]
    assert b[(1, 2021)] == 1.0  # median of 2018, 2019, 2020 -> 0, 1, 2
    assert np.isnan(b[(1, 2018)])  # no earlier years


def test_add_anomaly_fixed_and_trailing() -> None:
    df = pd.DataFrame({"area_id": "a", "date": pd.to_datetime(["2021-03-05"]), "log_chl": 0.5})
    fixed = pd.DataFrame({"area_id": ["a"], "month": [3], "baseline": [0.2]})
    trailing = pd.DataFrame({"area_id": ["a"], "month": [3], "year": [2021], "baseline": [0.1]})
    assert T.add_anomaly(df, fixed)["anomaly"].item() == pytest.approx(0.3)
    assert T.add_anomaly(df, trailing)["anomaly"].item() == pytest.approx(0.4)


def test_target_is_missing_when_window_too_cloudy() -> None:
    values = [np.nan] * 40
    values[5] = 1.0  # only one valid day in the windows of t = 0..4
    df = _series(values).assign(month=1)
    out = T.add_target(df, min_valid_days=2, train_end=pd.Timestamp("2030-01-01"))
    assert out["y"].isna().all()


def test_target_threshold_from_training_period_only() -> None:
    rng = np.random.default_rng(0)
    df = _series(list(rng.normal(size=800)), start="2021-01-01")
    df["month"] = df["date"].dt.month
    a = T.add_target(df, train_end=pd.Timestamp("2021-12-31"))
    df2 = df.copy()
    df2.loc[df2["date"] >= "2022-01-01", "anomaly"] += 50  # huge change after training
    b = T.add_target(df2, train_end=pd.Timestamp("2021-12-31"))
    # Thresholds unaffected (allclose: pandas rolling sums carry ~1e-15 float noise).
    np.testing.assert_allclose(a["threshold"], b["threshold"], rtol=0, atol=1e-9)
    # ...but the post-training labels do react to the new data
    assert b.loc[b["date"] >= "2022-02-01", "y"].mean() == 1.0
