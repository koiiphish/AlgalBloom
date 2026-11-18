"""Tests for ocean feature helpers (pipeline.features.ocean)."""

import numpy as np
import pandas as pd
import shapely

from pipeline.features import ocean as O


def test_run_length_above_counts_consecutive_days_ending_today() -> None:
    above = pd.Series([True, True, False, True, True, True, None])
    assert O.run_length_above(above).tolist() == [1, 2, 0, 1, 2, 3, 0]


def test_marine_heatwave_needs_five_days_and_uses_only_the_past() -> None:
    dates = pd.date_range("1991-01-01", "2021-12-31", freq="D")
    sst = pd.Series(15.0 + np.sin(np.arange(dates.size) / 58.1), index=dates)  # smooth cycle
    sst["2021-06-01":"2021-06-10"] += 5  # a 10-day warm event
    f = O.sst_features(sst)
    assert not f.loc["2021-06-04", "mhw"]  # day 4 of the event: not yet 5 days
    assert f.loc["2021-06-05", "mhw"]  # day 5: heatwave
    # The flag at a date must not change when the future changes.
    sst2 = sst.copy()
    sst2["2021-06-06":] += 10
    assert O.sst_features(sst2).loc[:"2021-06-05", "mhw"].equals(f.loc[:"2021-06-05", "mhw"])


def test_doy_climatology_wraps_year_end() -> None:
    dates = pd.date_range("2000-01-01", "2002-12-31", freq="D")
    s = pd.Series(np.where(dates.day_of_year <= 3, 10.0, 0.0), index=dates)
    clim = O.doy_climatology(s)
    # Day 366's window (+/- 5 days) reaches into early January, so it sees some 10s.
    assert clim[366] > 0
    assert clim[180] == 0


def test_nearest_valid_cells_skips_land_and_far_cells() -> None:
    lat = np.array([-43.0, -42.9])
    lon = np.array([147.0, 147.1, 147.2])
    valid = np.array([[False, True, True], [True, True, False]])  # False = land
    poly_m = shapely.Point(5_000_000, 5_000_000)  # far from everything (metric CRS)
    iy, ix, d = O.nearest_valid_cells(lat, lon, valid, poly_m, k=4, max_km=30)
    assert iy.size == 0 and d.size == 0  # nothing within 30 km

    import geopandas as gpd

    here = gpd.GeoSeries([shapely.Point(147.0, -43.0)], crs=4326).to_crs(O.METRIC_CRS)[0]
    iy, ix, d = O.nearest_valid_cells(lat, lon, valid, here, k=2, max_km=30)
    assert not np.any((lat[iy] == -43.0) & (lon[ix] == 147.0))  # land cell excluded
    assert d.size == 2 and np.all(np.diff(d) >= 0)  # sorted by distance
