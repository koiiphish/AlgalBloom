"""SST anomaly for the map layer and the popup context (decision C and the OSTIA choice in D014).

Anomaly = today's OSTIA near-real-time SST minus the 1991-2020 OSTIA reprocessed day-of-year
climatology (pipeline.model.sst_climatology). It is CONTEXT only: Phase 3 found that SST adds no
skill to this forecast (D013), and the popup says so.

Caveat: the climatology comes from the reprocessed product and today's value from the
near-real-time one. They are the same analysis system, but small offsets are possible (D014).
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from pipeline.features.areas import METRIC_CRS
from pipeline.features.ocean import nearest_valid_cells
from pipeline.model.sst_climatology import for_day

GRID_TOL_DEG = 0.01  # NRT and climatology grids must match to within this


def _nearest_index(src: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Index of the nearest `src` coordinate for each target coordinate."""
    order = np.argsort(src)
    pos = np.clip(np.searchsorted(src[order], targets), 1, src.size - 1)
    left, right = src[order][pos - 1], src[order][pos]
    return order[np.where(np.abs(targets - left) <= np.abs(targets - right), pos - 1, pos)]


def anomaly_grid(path, clim: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.Timestamp]:
    """(lat, lon, anomaly in deg C, date) for the newest day in an OSTIA NRT file."""
    with xr.open_dataset(path) as ds:
        da = ds.analysed_sst.isel(time=-1)
        sst = da.values.astype(float) - 273.15
        lat, lon = ds.latitude.values, ds.longitude.values
        day = pd.Timestamp(da.time.values).normalize()
    iy, ix = _nearest_index(clim["lat"], lat), _nearest_index(clim["lon"], lon)
    if max(np.abs(clim["lat"][iy] - lat).max(), np.abs(clim["lon"][ix] - lon).max()) > GRID_TOL_DEG:
        raise ValueError("OSTIA NRT grid does not match the stored climatology grid")
    base = for_day(clim, day.day_of_year)[np.ix_(iy, ix)]
    return lat, lon, sst - base, day


def area_anomalies(lat, lon, anom: np.ndarray, areas: gpd.GeoDataFrame) -> pd.Series:
    """Per-area SST anomaly: mean of the 4 nearest valid cells within 30 km (as in Phase 2)."""
    valid = np.isfinite(anom)
    out = {}
    for area_id, poly in zip(areas.area_id, areas.to_crs(METRIC_CRS).geometry, strict=True):
        iy, ix, _ = nearest_valid_cells(lat, lon, valid, poly)
        out[area_id] = float(np.mean(anom[iy, ix])) if iy.size else np.nan
    return pd.Series(out, name="sst_anom")
