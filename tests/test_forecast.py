"""Phase 4 daily forecast: parity with training, leakage, archive, stale handling, rasters."""

import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from pipeline.features import target as T
from pipeline.features.chl_features import build_chl_features
from pipeline.forecast import archive, score
from pipeline.model.calibrate import Calibrator
from pipeline.model.persistence import SCORE
from pipeline.model.sst_climatology import doy_mean_grid, for_day
from pipeline.publish import rasters, site

ISSUE = pd.Timestamp("2026-03-31")


def _chl(seed: int = 0, days: int = 60) -> pd.DataFrame:
    """Two areas of synthetic daily stats, with cloudy gaps and partly cloudy days."""
    rng = np.random.default_rng(seed)
    rows = []
    for area in ("tas:a:1", "tas:b:2"):
        for d in pd.date_range(ISSUE - pd.Timedelta(days=days - 1), ISSUE):
            if rng.random() < 0.4:
                continue  # no row at all = cloudy
            rows.append({"area_id": area, "date": d, "chl": float(rng.lognormal(1, 0.5)),
                         "n_valid": int(rng.integers(0, 40)), "n_pixels": 40})  # fmt: skip
    return pd.DataFrame(rows)


def _deployment() -> score.Deployment:
    """A small deployment with a simple calibrator and a flat baseline."""
    base = pd.DataFrame([{"area_id": a, "month": m, "baseline": 0.4}
                         for a in ("tas:a:1", "tas:b:2") for m in range(1, 13)])  # fmt: skip
    clim = base.rename(columns={"baseline": "clim_rate"}).assign(clim_rate=0.1)
    return score.Deployment(
        model_version="test", calibrator=Calibrator(x=[-1.0, 1.0], y=[0.0, 1.0]),
        cutoffs={"moderate": 0.6, "high": 0.8}, baseline=base, climatology=clim,
        min_valid_pixels=5,
    )  # fmt: skip


def test_daily_score_matches_training_path():
    """The daily path must give exactly the training pipeline's score for the issue date."""
    chl, dep = _chl(), _deployment()
    today, _ = score.run(chl, dep, ["tas:a:1", "tas:b:2"], ISSUE, history_days=20)
    base = T.add_log_chl(T.complete_daily_index(chl))
    anoms = T.add_anomaly(base, dep.baseline)
    feats = build_chl_features(anoms[["area_id", "date", "anomaly", "log_chl", "weight"]])
    expected = feats[feats.date == ISSUE].set_index("area_id")[SCORE]
    got = today.set_index("area_id")[SCORE]
    pd.testing.assert_series_equal(got.sort_index(), expected.sort_index(), check_names=False)


def test_score_ignores_data_after_t_minus_2():
    """Changing chl on t-1 and t must not change the forecast issued on t (no leakage)."""
    chl, dep = _chl(seed=1), _deployment()
    ids = ["tas:a:1", "tas:b:2"]
    a, _ = score.run(chl, dep, ids, ISSUE, history_days=10)
    late = chl["date"] >= ISSUE - pd.Timedelta(days=1)
    b, _ = score.run(chl.assign(chl=np.where(late, 999.0, chl["chl"])), dep, ids, ISSUE, 10)
    pd.testing.assert_series_equal(a[SCORE], b[SCORE])
    pd.testing.assert_series_equal(a["p"], b["p"])


def test_no_clear_view_falls_back_to_climatology():
    """An area with no clear day in the 14-day window gets the climatology rate, flagged."""
    chl, dep = _chl(seed=2), _deployment()
    window = chl["date"] >= ISSUE - pd.Timedelta(days=20)
    chl = chl[~(window & (chl["area_id"] == "tas:a:1"))]
    today, _ = score.run(chl, dep, ["tas:a:1", "tas:b:2"], ISSUE, history_days=5)
    row = today.set_index("area_id").loc["tas:a:1"]
    assert row["stale_chl"] and row["p"] == pytest.approx(0.1)
    assert row["clear_days14"] == 0 and row["trend"] == "unknown"


def test_trend_words():
    """Rising when the newer half of the window is clearly above the older half."""
    days = pd.date_range(ISSUE - pd.Timedelta(days=15), ISSUE - pd.Timedelta(days=2))
    anoms = pd.DataFrame({"area_id": "x", "date": days, "weight": 1.0, "log_chl": 1.0,
                          "anomaly": np.where(days >= ISSUE - pd.Timedelta(days=8), 0.3, 0.0)})  # fmt: skip
    ev = score.evidence(anoms, ISSUE).iloc[0]
    assert ev["trend"] == "rising" and ev["clear_days14"] == 14
    assert ev["recent7_anom"] == pytest.approx(0.3) and ev["prior7_anom"] == pytest.approx(0.0)


def test_archive_upserts():
    """Newer chl values replace older ones; a same-day rerun replaces that day's forecasts."""
    old = pd.DataFrame({"area_id": ["a", "a"], "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
                        "chl": [1.0, 2.0], "n_valid": 5, "n_pixels": 9, "chl_core": 1.0,
                        "n_core": 3, "source": "my", "retrieved_utc": "t0"})  # fmt: skip
    new = old.iloc[[1]].assign(chl=3.0, source="nrt", retrieved_utc="t1")
    out = archive.upsert_chl(old, new)
    assert len(out) == 2 and out.loc[out.date == "2026-01-02", "chl"].item() == 3.0
    fc = pd.DataFrame({c: [0] for c in archive.FORECAST_COLS}).assign(issue_date="2026-01-03",
                                                                       area_id="a", p=0.1)  # fmt: skip
    again = archive.upsert_forecasts(fc, fc.assign(p=0.2))
    assert len(again) == 1 and again["p"].item() == 0.2


def test_keep_previous_marks_stale_and_keeps_since(tmp_path):
    """On input failure yesterday's files are kept, flagged stale, and stale_since persists."""
    prev, out = tmp_path / "prev", tmp_path / "site"
    prev.mkdir()
    out.mkdir()
    (prev / "areas.geojson").write_text("{}")
    site.write_json(prev / "status.json", {"run_utc": "2026-01-01T22:00:00+00:00",
                                           "stale": True, "stale_since": "2025-12-31"})  # fmt: skip
    st = site.keep_previous(prev, out, "boom", datetime(2026, 1, 2, tzinfo=UTC), ISSUE)
    assert (out / "areas.geojson").exists() and st["stale"] and st["stale_since"] == "2025-12-31"
    assert json.loads((out / "status.json").read_text())["stale_reason"] == "boom"


def test_history_window_is_pruned(tmp_path):
    """Only the newest HISTORY_KEEP dated snapshots survive."""
    prev, out = tmp_path / "prev", tmp_path / "site"
    for i in range(1, 10):
        (prev / "history" / f"2026-01-0{i}").mkdir(parents=True)
    out.mkdir()
    (out / "areas.geojson").write_text("{}")
    site.carry_history(prev, out, pd.Timestamp("2026-01-10"))
    kept = sorted(p.name for p in (out / "history").iterdir())
    assert len(kept) == site.HISTORY_KEEP and kept[-1] == "2026-01-10"


def test_mercator_resample_is_north_up_and_keeps_edges():
    """Rows come out north-first, and the image edges are the outer pixel edges."""
    lat = np.array([-44.0, -43.5, -43.0])  # south to north, as in the files
    vals = np.array([[1.0], [2.0], [3.0]])
    img, north, south = rasters.to_north_up_mercator(vals, lat)
    assert img[0, 0] == 3.0 and img[-1, 0] == 1.0
    assert north == pytest.approx(-42.75) and south == pytest.approx(-44.25)


def test_colourise_makes_nan_transparent():
    """Land and cloud (NaN) must be fully transparent."""
    from matplotlib.colors import Normalize

    rgba = rasters.colourise(np.array([[np.nan, 0.0]]), rasters.SST_STOPS, Normalize(-1, 1))
    assert rgba[0, 0, 3] == 0 and rgba[0, 1, 3] > 0


def test_sst_climatology_pooling_and_interpolation():
    """Pooled DOY mean is the plain mean of the window; interpolation wraps the year end."""
    doy = np.arange(1, 367)
    sst = doy.astype(float).reshape(-1, 1, 1)  # value = day of year
    clim = doy_mean_grid(sst, doy, window=3)
    assert clim[9, 0, 0] == pytest.approx(10.0)  # mean of days 9, 10, 11
    c = {"doy": np.array([1, 361]), "clim": np.array([[[0.0]], [[10.0]]])}
    assert for_day(c, 361)[0, 0] == pytest.approx(10.0)
    assert for_day(c, 364)[0, 0] == pytest.approx(10.0 * (1 - 3 / 6))  # 3 of 6 days to day 1
