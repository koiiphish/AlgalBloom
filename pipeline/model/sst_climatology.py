"""Gridded 1991-2020 SST climatology for the SST-anomaly map layer (Phase 4, D014).

Same definition as the Phase 2 SST features (pipeline.features.ocean): OSTIA reprocessed SST,
1991-2020, day-of-year mean pooled over a centred 11-day window. Here it is computed per grid
cell, for the two map boxes, and stored compactly so the daily job needs no history:
  - every STEP_DAYS-th day of year (the 11-day smoothing makes the curve smooth; the daily job
    interpolates linearly between stored days, wrapping at the year end)
  - int16 hundredths of a degree C, with -32768 for land

Run:  uv run python -m pipeline.model.sst_climatology
Output: models/sst_clim_tas.npz, models/sst_clim_sa.npz
"""

from pathlib import Path

import numpy as np
import xarray as xr

from pipeline.config import RAW_DIR, REPO_ROOT
from pipeline.features.ocean import CLIM_END, CLIM_START, DOY_WINDOW

SOURCES = {
    "tas": RAW_DIR / "copernicus" / "history_ocean_tas" / "ostia_rep.nc",
    "sa": RAW_DIR / "copernicus" / "history_sst_map_sa" / "ostia_rep.nc",
}
STEP_DAYS = 5
FILL = -32768


def out_path(region: str) -> Path:
    """models/sst_clim_<region>.npz"""
    return REPO_ROOT / "models" / f"sst_clim_{region}.npz"


def doy_mean_grid(sst: np.ndarray, doy: np.ndarray, window: int = DOY_WINDOW) -> np.ndarray:
    """(366, lat, lon) day-of-year mean, pooling all days within +/- window//2 (wrapping).

    Pooling is done with per-day-of-year sums and counts, so it equals averaging every
    individual day in the window (the same pooled mean as pipeline.features.ocean).
    """
    ny, nx = sst.shape[1:]
    sums, counts = np.zeros((366, ny, nx)), np.zeros((366, ny, nx))
    ok = np.isfinite(sst)
    for d in range(1, 367):
        sel = doy == d
        sums[d - 1] = np.where(ok[sel], sst[sel], 0.0).sum(axis=0)
        counts[d - 1] = ok[sel].sum(axis=0)
    half = window // 2
    idx = (np.arange(366)[:, None] + np.arange(-half, half + 1)[None, :]) % 366
    with np.errstate(invalid="ignore"):
        return sums[idx].sum(axis=1) / counts[idx].sum(axis=1)


def build(region: str) -> dict[str, np.ndarray]:
    """Climatology arrays for one region box."""
    with xr.open_dataset(SOURCES[region]) as ds:
        da = ds.analysed_sst.sel(time=slice(CLIM_START, CLIM_END))
        sst = da.values.astype(np.float32) - 273.15
        doy = da.time.dt.dayofyear.values
        lat, lon = ds.latitude.values, ds.longitude.values
    clim = doy_mean_grid(sst, doy)
    days = np.arange(1, 367, STEP_DAYS)
    stored = clim[days - 1]
    packed = np.where(np.isfinite(stored), np.round(stored * 100), FILL).astype(np.int16)
    return {"lat": lat.astype(np.float32), "lon": lon.astype(np.float32), "doy": days,
            "clim_centi_c": packed}  # fmt: skip


def load(path: Path) -> dict[str, np.ndarray]:
    """Read a stored climatology (lat, lon, doy, clim in deg C with NaN for land)."""
    with np.load(path) as z:
        clim = np.where(z["clim_centi_c"] == FILL, np.nan, z["clim_centi_c"] / 100.0)
        return {"lat": z["lat"], "lon": z["lon"], "doy": z["doy"], "clim": clim}


def for_day(c: dict[str, np.ndarray], day_of_year: int) -> np.ndarray:
    """Climatology for one day of year: linear interpolation between stored days, wrapping."""
    doy = c["doy"]
    i = np.searchsorted(doy, day_of_year, side="right") - 1  # stored day at or before
    j = (i + 1) % doy.size
    span = (doy[j] - doy[i]) % 366 or 366
    w = ((day_of_year - doy[i]) % 366) / span
    return (1 - w) * c["clim"][i] + w * c["clim"][j]


def main() -> None:
    """Build and save both regions."""
    for region in SOURCES:
        arrays = build(region)
        np.savez_compressed(out_path(region), **arrays)
        c = load(out_path(region))
        print(f"{region}: grid {c['clim'].shape[1:]}, {c['doy'].size} stored days, "
              f"{out_path(region).stat().st_size / 1e6:.1f} MB, "
              f"mean 1 Jan {np.nanmean(for_day(c, 1)):.2f} C, "
              f"1 Aug {np.nanmean(for_day(c, 213)):.2f} C")  # fmt: skip


if __name__ == "__main__":
    main()
