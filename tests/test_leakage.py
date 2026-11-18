"""Leakage tests: a feature for issue date t must not change when data after t - lag changes.

These are the brief's explicit "no feature uses data after issue date t" tests, made
stricter by the operational availability lags in pipeline/features/availability.py.
"""

import numpy as np
import pandas as pd
import pytest

from pipeline.features.availability import CHL_LAG_DAYS
from pipeline.features.chl_features import area_chl_features


def _anoms(seed: int = 0, n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    a = rng.normal(size=n)
    a[rng.random(n) < 0.5] = np.nan  # ~50% cloudy days
    return pd.DataFrame(
        {
            "area_id": "a",
            "date": pd.date_range("2020-01-01", periods=n, freq="D"),
            "anomaly": a,
            "log_chl": a + 0.3,
        }
    )


@pytest.mark.parametrize("t", [20, 50, 90])
def test_chl_features_ignore_data_after_t_minus_lag(t: int) -> None:
    base = _anoms()
    changed = base.copy()
    cutoff = t - CHL_LAG_DAYS  # last index the features may use
    changed.loc[cutoff + 1 :, ["anomaly", "log_chl"]] = 99.0  # includes day t-1 and day t
    f0 = area_chl_features(base).iloc[t]
    f1 = area_chl_features(changed).iloc[t]
    pd.testing.assert_series_equal(f0, f1)


def test_chl_features_do_react_to_data_at_t_minus_lag() -> None:
    """Sanity check that the test above isn't passing vacuously."""
    t = 50
    base = _anoms()
    base.loc[t - CHL_LAG_DAYS, ["anomaly", "log_chl"]] = 0.0
    changed = base.copy()
    changed.loc[t - CHL_LAG_DAYS, ["anomaly", "log_chl"]] = 5.0
    assert area_chl_features(changed).iloc[t]["chl_anom_last"] == 5.0
    assert area_chl_features(base).iloc[t]["chl_anom_last"] == 0.0


def test_days_since_obs_counts_from_issue_date() -> None:
    df = _anoms()
    df["anomaly"] = np.nan
    df.loc[40, "anomaly"] = 1.0
    f = area_chl_features(df)
    assert f.iloc[40 + CHL_LAG_DAYS]["chl_days_since_obs"] == CHL_LAG_DAYS
    assert f.iloc[45 + CHL_LAG_DAYS]["chl_days_since_obs"] == CHL_LAG_DAYS + 5


def _daily_weather(n: int = 60, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    cols = ["wind_u", "wind_v", "wind_speed", "radiation_mj", "air_temp", "rain_mm"]
    return pd.DataFrame(rng.random((n, len(cols))), index=idx, columns=cols)


def test_past_weather_features_ignore_data_after_t_minus_lag() -> None:
    from pipeline.features.availability import WEATHER_LAG_DAYS
    from pipeline.features.weather import area_weather_features

    t = 40
    base = _daily_weather()
    changed = base.copy()
    changed.iloc[t - WEATHER_LAG_DAYS + 1 :] = 99.0
    past_cols = [c for c in area_weather_features(base).columns if not c.startswith("fc7_")]
    f0 = area_weather_features(base)[past_cols].iloc[t]
    f1 = area_weather_features(changed)[past_cols].iloc[t]
    pd.testing.assert_series_equal(f0, f1)


def test_forecast_window_features_use_only_t_plus_1_to_t_plus_7() -> None:
    from pipeline.features.weather import area_weather_features

    t = 30
    base = _daily_weather()
    changed = base.copy()
    changed.iloc[: t + 1] = 99.0  # everything up to and including day t
    changed.iloc[t + 8 :] = 99.0  # everything from day t+8
    fc_cols = [c for c in area_weather_features(base).columns if c.startswith("fc7_")]
    f0 = area_weather_features(base)[fc_cols].iloc[t]
    f1 = area_weather_features(changed)[fc_cols].iloc[t]
    pd.testing.assert_series_equal(f0, f1)


def test_wind_components_follow_meteorological_convention() -> None:
    from pipeline.features.weather import wind_components

    u, v = wind_components(pd.Series([10.0, 10.0]), pd.Series([0.0, 270.0]))
    assert v[0] == pytest.approx(-10.0)  # wind FROM the north blows southward
    assert u[1] == pytest.approx(10.0)  # wind FROM the west blows eastward
