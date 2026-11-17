"""Helpers for pulling small regional subsets from THREDDS/OPeNDAP servers (e.g. AODN).

OPeNDAP lets us request only the lat/lon window we need, so a ~2 GB Australia-wide
file becomes a few MB per region without downloading the whole thing.
"""

from pathlib import Path

import xarray as xr

from pipeline.config import BBox


def lat_slice(lat: xr.DataArray, south: float, north: float) -> slice:
    """Return a slice that selects [south, north] whatever the latitude ordering.

    Some IMOS grids store latitude north->south (descending), others south->north.
    xarray's label slicing must follow the stored order, so we flip as needed.
    """
    descending = float(lat[0]) > float(lat[-1])
    return slice(north, south) if descending else slice(south, north)


def subset_bbox(ds: xr.Dataset, bbox: BBox, lat_name: str, lon_name: str) -> xr.Dataset:
    """Cut a dataset down to a lon/lat bounding box."""
    return ds.sel(
        {
            lat_name: lat_slice(ds[lat_name], bbox.south, bbox.north),
            lon_name: slice(bbox.west, bbox.east),
        }
    )


def fetch_subset(
    url: str,
    variables: list[str],
    bbox: BBox,
    out_path: Path,
    lat_name: str = "lat",
    lon_name: str = "lon",
) -> Path:
    """Open a remote OPeNDAP dataset, subset variables + bbox, and save it as NetCDF.

    Skips the download if `out_path` already exists (simple cache).
    """
    if out_path.exists():
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with xr.open_dataset(url, decode_timedelta=False) as ds:
        sub = subset_bbox(ds[variables], bbox, lat_name, lon_name).load()
    sub.to_netcdf(out_path)
    return out_path
