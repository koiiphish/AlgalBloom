"""Ocean features per area: SST, SST anomaly, marine-heatwave state, mixed-layer depth, currents.

Gridded products barely reach the small coastal harvest areas (Phase 0), so each area uses
the K nearest *valid ocean* grid cells within MAX_KM of its polygon, and the distance is
recorded as a data-quality feature.

  - SST: OSTIA (Copernicus), reprocessed to 2026-06-30, near-real-time after that
  - SST climatology and marine-heatwave threshold: 1991-2020, day-of-year with an 11-day
    window (Hobday et al. 2016). This baseline period is entirely before validation/test.
  - Marine heatwave at issue time t: SST above the 90th-percentile threshold for >= 5
    CONSECUTIVE days ENDING at t. (Hobday's definition also flags the first 4 days of an
    event, which needs future data; the run-length form here uses only the past.)
  - Mixed-layer depth and surface current speed: GLORYS12 reanalysis

Run:  uv run python -m pipeline.features.ocean
Output: data/interim/ocean_area_day.parquet
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr

from pipeline.config import DATA_DIR, RAW_DIR
from pipeline.features.areas import METRIC_CRS, load_tas_areas

OCEAN_DIR = RAW_DIR / "copernicus" / "history_ocean_tas"
OUT_PATH = DATA_DIR / "interim" / "ocean_area_day.parquet"
K_CELLS = 4
MAX_KM = 30.0
CLIM_START, CLIM_END = "1991-01-01", "2020-12-31"
MHW_MIN_DAYS = 5
MHW_QUANTILE = 0.90
DOY_WINDOW = 11  # days, centred


def nearest_valid_cells(
    lat: np.ndarray, lon: np.ndarray, valid: np.ndarray, polygon_m: shapely.Geometry,
    k: int = K_CELLS, max_km: float = MAX_KM,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:  # fmt: skip
    """Indices (iy, ix) and distances (km) of the k valid cells closest to a polygon.

    `valid` is a (lat, lon) boolean mask of ocean cells; `polygon_m` is in METRIC_CRS.
    Cells further than `max_km` are dropped (may return fewer than k, or none).
    """
    iy, ix = np.nonzero(valid)
    pts = gpd.GeoSeries(gpd.points_from_xy(lon[ix], lat[iy]), crs=4326).to_crs(METRIC_CRS)
    dist_km = pts.distance(polygon_m).to_numpy() / 1000
    order = np.argsort(dist_km)[:k]
    keep = order[dist_km[order] <= max_km]
    return iy[keep], ix[keep], dist_km[keep]


def doy_climatology(s: pd.Series, quantile: float | None = None) -> pd.Series:
    """Day-of-year climatology (mean, or a quantile) using a centred DOY_WINDOW-day window.

    Pools all values whose day-of-year is within +/- DOY_WINDOW//2 days (wrapping at
    year end). Returns a Series indexed by day-of-year 1..366.
    """
    doy = s.index.day_of_year.to_numpy()
    vals = s.to_numpy()
    half = DOY_WINDOW // 2
    out = {}
    for d in range(1, 367):
        delta = np.abs(doy - d)
        near = np.minimum(delta, 366 - delta) <= half
        v = vals[near & np.isfinite(vals)]
        out[d] = (
            (np.quantile(v, quantile) if quantile is not None else v.mean()) if v.size else np.nan
        )
    return pd.Series(out)


def run_length_above(above: pd.Series) -> pd.Series:
    """Number of consecutive True values ending at each position (0 where False).

    Uses only the current and earlier values, so it is safe at issue time.
    """
    a = above.fillna(False).astype(bool).to_numpy()
    out = np.zeros(a.size, dtype=int)
    run = 0
    for i, v in enumerate(a):
        run = run + 1 if v else 0
        out[i] = run
    return pd.Series(out, index=above.index)


def sst_features(sst: pd.Series) -> pd.DataFrame:
    """SST (deg C), anomaly vs 1991-2020 DOY climatology, and marine-heatwave run state."""
    base = sst[CLIM_START:CLIM_END]
    clim = doy_climatology(base)
    thr = doy_climatology(base, MHW_QUANTILE)
    doy = sst.index.day_of_year
    anom = sst - clim.reindex(doy).to_numpy()
    above = sst > thr.reindex(doy).to_numpy()
    run = run_length_above(above)
    return pd.DataFrame(
        {"sst": sst, "sst_anom": anom, "mhw_run_days": run, "mhw": (run >= MHW_MIN_DAYS)}
    )


def _series_for_area(da: xr.DataArray, iy: np.ndarray, ix: np.ndarray) -> pd.Series:
    """Daily mean of a (time, lat, lon) variable over the selected cells."""
    vals = da.values[:, iy, ix]
    with np.errstate(all="ignore"):
        m = np.nanmean(vals, axis=1) if vals.shape[1] else np.full(vals.shape[0], np.nan)
    return pd.Series(m, index=pd.to_datetime(da.time.values).normalize())


def merged_ostia() -> xr.DataArray:
    """OSTIA SST in deg C: reprocessed where available, near-real-time afterwards."""
    rep = xr.open_dataset(OCEAN_DIR / "ostia_rep.nc").analysed_sst - 273.15
    nrt = xr.open_dataset(OCEAN_DIR / "ostia_nrt.nc").analysed_sst - 273.15
    nrt_after = nrt.sel(time=slice(rep.time.values[-1] + np.timedelta64(1, "D"), None))
    return xr.concat([rep, nrt_after], dim="time")


def build() -> pd.DataFrame:
    """Area x day ocean feature table for all Tas areas."""
    areas = load_tas_areas()
    polys_m = areas.to_crs(METRIC_CRS).geometry
    sst = merged_ostia()
    g2 = xr.open_dataset(OCEAN_DIR / "glorys_2d.nc").mlotst
    gs = xr.open_dataset(OCEAN_DIR / "glorys_surface.nc").isel(depth=0)
    speed = np.hypot(gs.uo, gs.vo)
    sst_valid = np.isfinite(sst.isel(time=-1).values)
    glo_valid = np.isfinite(g2.isel(time=0).values)
    parts = []
    for area_id, poly in zip(areas.area_id, polys_m, strict=True):
        iy, ix, d_sst = nearest_valid_cells(sst.latitude.values, sst.longitude.values,
                                            sst_valid, poly)  # fmt: skip
        f = sst_features(_series_for_area(sst, iy, ix))
        jy, jx, d_glo = nearest_valid_cells(g2.latitude.values, g2.longitude.values,
                                            glo_valid, poly)  # fmt: skip
        f = f.join(_series_for_area(g2, jy, jx).rename("mld"), how="left")
        f = f.join(_series_for_area(speed, jy, jx).rename("current_speed"), how="left")
        f["sst_cell_km"] = d_sst.mean() if d_sst.size else np.nan
        f["model_cell_km"] = d_glo.mean() if d_glo.size else np.nan
        f.insert(0, "area_id", area_id)
        parts.append(f[f.index >= "2016-01-01"])
    out = pd.concat(parts).rename_axis("date").reset_index()
    return out


def main() -> None:
    """Build, save and summarise."""
    df = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(f"wrote {len(df):,} rows -> {OUT_PATH}")
    per_area = df.groupby("area_id")[["sst_cell_km", "model_cell_km"]].first()
    print("distance to nearest cells (km):")
    print(per_area.describe().round(1).to_string())
    print("missing share:", df[["sst", "mld", "current_speed"]].isna().mean().round(3).to_dict())
    print("MHW days share by year:", df.groupby(df.date.dt.year).mhw.mean().round(3).to_dict())


if __name__ == "__main__":
    main()
