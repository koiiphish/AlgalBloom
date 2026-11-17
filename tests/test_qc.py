"""Tests for pipeline.qc and the OPeNDAP bbox helpers."""

import numpy as np
import xarray as xr

from pipeline.config import BBox
from pipeline.fetch.opendap import subset_bbox
from pipeline.qc import mask_invalid_chl, valid_fraction


def test_mask_invalid_chl_removes_fill_and_nonpositive() -> None:
    chl = xr.DataArray([-999.0, 0.0, 0.25, np.nan, 3.0])
    out = mask_invalid_chl(chl).values
    assert np.isnan(out[[0, 1, 3]]).all()
    assert out[2] == 0.25 and out[4] == 3.0


def test_valid_fraction() -> None:
    assert valid_fraction(xr.DataArray([1.0, np.nan, 2.0, np.nan])) == 0.5
    assert valid_fraction(xr.DataArray(np.array([]))) == 0.0


def _grid(lat: np.ndarray) -> xr.Dataset:
    lon = np.arange(130.0, 141.0, 1.0)
    return xr.Dataset(
        {"v": (("lat", "lon"), np.zeros((lat.size, lon.size)))},
        coords={"lat": lat, "lon": lon},
    )


def test_subset_bbox_handles_both_latitude_orders() -> None:
    bbox = BBox("t", west=132.0, south=-36.0, east=134.0, north=-34.0)
    for lat in (np.arange(-40.0, -29.0, 1.0), np.arange(-30.0, -41.0, -1.0)):
        sub = subset_bbox(_grid(lat), bbox, "lat", "lon")
        assert sorted(sub.lat.values.tolist()) == [-36.0, -35.0, -34.0]
        assert sub.lon.values.tolist() == [132.0, 133.0, 134.0]
