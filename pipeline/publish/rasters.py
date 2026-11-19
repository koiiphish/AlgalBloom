"""Render the map layers as PNG images plus a small JSON describing them (Phase 4).

MapLibre shows a PNG as an "image source" stretched between four corner coordinates, and it
stretches linearly in Web Mercator. The satellite grids are regular in latitude, so rows are
resampled to equal Mercator spacing first; otherwise the image would be misplaced by up to a
few kilometres mid-box.

Colours (validated design palette, see the dataviz guidance):
  - chlorophyll: one-hue sequential green, log scale (light = low, dark = high)
  - SST anomaly: diverging blue - neutral grey - red, symmetric about 0
"""

from pathlib import Path

import matplotlib
import numpy as np
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap, LogNorm, Normalize

matplotlib.use("Agg")  # no display in GitHub Actions
import matplotlib.image as mpimg  # noqa: E402  (after choosing the backend)

CHL_RANGE = (0.1, 30.0)  # mg m-3, log scale
SST_ANOM_RANGE = (-3.0, 3.0)  # deg C
CHL_STOPS = ["#e6f2df", "#9fd08f", "#4fa34a", "#1f7a2e", "#0b4d1c"]
SST_STOPS = ["#104281", "#6da7ec", "#f0efec", "#ef8f8e", "#a52524"]
CHL_COMPOSITE_DAYS = 7


def _merc_y(lat: np.ndarray) -> np.ndarray:
    """Web Mercator y (unitless) for latitudes in degrees."""
    return np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def _inv_merc_y(y: np.ndarray) -> np.ndarray:
    """Latitude in degrees for Web Mercator y."""
    return np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)


def to_north_up_mercator(values: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Resample (lat, lon) rows to equal Mercator spacing, north at the top.

    Returns the resampled array and the north/south edges (degrees) of the image.
    """
    order = np.argsort(lat)[::-1]  # north first
    lat_s, vals = lat[order], values[order]
    half = abs(lat_s[0] - lat_s[1]) / 2
    north, south = lat_s[0] + half, lat_s[-1] - half
    y_edges = np.linspace(_merc_y(north), _merc_y(south), lat_s.size + 1)
    row_lat = _inv_merc_y((y_edges[:-1] + y_edges[1:]) / 2)
    src = np.abs(lat_s[None, :] - row_lat[:, None]).argmin(axis=1)
    return vals[src], float(north), float(south)


def colourise(values: np.ndarray, stops: list[str], norm) -> np.ndarray:
    """RGBA uint8 image; NaN (land, cloud) becomes fully transparent."""
    cmap = LinearSegmentedColormap.from_list("layer", stops)
    rgba = cmap(norm(np.ma.masked_invalid(values)), bytes=True)
    rgba[..., 3] = np.where(np.isfinite(values), 230, 0)
    return rgba


def sea_connected(land: np.ndarray) -> np.ndarray:
    """True for water pixels connected (8-neighbour) to the edge of the box, i.e. the sea.

    OLCI flags mark land only, so inland lakes count as water and show chlorophyll. Lakes are
    water bodies enclosed by land; estuaries such as the Derwent and Tamar touch the sea and
    are kept. Channels narrower than one 300 m pixel can disconnect an upper estuary.
    """
    from scipy import ndimage

    labels, _ = ndimage.label(~land, structure=np.ones((3, 3), dtype=bool))
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    return np.isin(labels, border[border > 0])


def chl_composite(path: Path, days: int = CHL_COMPOSITE_DAYS):
    """Median chl over the newest `days` days in an OLCI file, sea pixels only:
    (lat, lon, values, first, last)."""
    with xr.open_dataset(path) as ds:
        da = ds.CHL.isel(time=slice(-days, None))
        vals = da.where(da > 0).median("time", skipna=True).values
        if "flags" in ds:
            land = (ds.flags.values == 1).any(axis=0)
            vals = np.where(sea_connected(land), vals, np.nan)
        t = da.time.values
        return ds.latitude.values, ds.longitude.values, vals, t[0], t[-1]


def write_layer(values: np.ndarray, lat: np.ndarray, lon: np.ndarray, kind: str,
                out_png: Path) -> dict:  # fmt: skip
    """Write one PNG and return its MapLibre corner coordinates and legend."""
    if kind == "chl":
        norm, stops, rng, unit = LogNorm(*CHL_RANGE, clip=True), CHL_STOPS, CHL_RANGE, "mg m-3"
    else:
        norm, stops, rng, unit = (
            Normalize(*SST_ANOM_RANGE, clip=True),
            SST_STOPS,
            SST_ANOM_RANGE,
            "deg C",
        )
    img, north, south = to_north_up_mercator(values, lat)
    half_x = abs(lon[1] - lon[0]) / 2
    west, east = float(lon.min() - half_x), float(lon.max() + half_x)
    order = np.argsort(lon)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    mpimg.imsave(out_png, colourise(img[:, order], stops, norm))
    return {
        "file": out_png.name,
        # MapLibre order: top-left, top-right, bottom-right, bottom-left, as [lon, lat]
        "coordinates": [[west, north], [east, north], [east, south], [west, south]],
        "legend": {
            "stops": stops,
            "range": list(rng),
            "unit": unit,
            "scale": "log" if kind == "chl" else "linear",
        },  # fmt: skip
    }
