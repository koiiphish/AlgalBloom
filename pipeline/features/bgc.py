"""Baseline 3 input: Copernicus BGC model chlorophyll per area, as a forward-window anomaly.

For area a and issue date t:
  bgc_fwd_anom = mean(log10 BGC chl over t+1..t+7) - median(log10 BGC chl, same area and
                 calendar month, training years only)
That is the same construction as our target (docs/target_definition.md), applied to the
model's chlorophyll instead of the satellite's. It uses the model's best estimate for
t+1..t+7 (a "perfect forecast"; no issued-forecast archive exists, D012), which flatters
this baseline.

Run:  uv run python -m pipeline.features.bgc
Output: data/interim/bgc_area_day.parquet
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from pipeline.config import DATA_DIR, RAW_DIR
from pipeline.features.areas import METRIC_CRS, load_tas_areas
from pipeline.features.ocean import _series_for_area, nearest_valid_cells
from pipeline.features.target import TRAIN_END, forward_window

BGC_DIR = RAW_DIR / "copernicus" / "history_bgc"
OUT_PATH = DATA_DIR / "interim" / "bgc_area_day.parquet"
MAX_KM = 50.0  # 0.25 deg cells (~25 km) rarely lie within 30 km of a sheltered bay


def bgc_chl(region: str = "tas") -> xr.DataArray:
    """Surface BGC chl (time, latitude, longitude), mg m-3."""
    return xr.open_dataset(BGC_DIR / f"{region}_bgc_chl.nc").chl.isel(depth=0)


def area_bgc(daily_chl: pd.Series, train_end: str = TRAIN_END) -> pd.DataFrame:
    """Forward-window BGC anomaly for one area (daily index)."""
    log = np.log10(daily_chl.where(daily_chl > 0)).asfreq("D")
    train = log[log.index <= pd.Timestamp(train_end)]
    clim = train.groupby(train.index.month).median()
    anom = log - log.index.month.map(clim).to_numpy()
    fwd, _ = forward_window(anom)
    return pd.DataFrame({"bgc_anom": anom, "bgc_fwd_anom": fwd})


def build(areas: gpd.GeoDataFrame | None = None, region: str = "tas") -> pd.DataFrame:
    """Area x day BGC baseline inputs for every area polygon."""
    areas = load_tas_areas() if areas is None else areas
    chl = bgc_chl(region)
    valid = np.isfinite(chl.isel(time=0).values)
    parts = []
    for area_id, poly in zip(areas.area_id, areas.to_crs(METRIC_CRS).geometry, strict=True):
        iy, ix, dist = nearest_valid_cells(
            chl.latitude.values, chl.longitude.values, valid, poly, max_km=MAX_KM
        )
        if iy.size == 0:
            continue
        f = area_bgc(_series_for_area(chl, iy, ix))
        f["bgc_cell_km"] = dist.mean()
        f.insert(0, "area_id", area_id)
        parts.append(f)
    return pd.concat(parts).rename_axis("date").reset_index()


def main() -> None:
    """Build, save and summarise."""
    df = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    km = df.groupby("area_id").bgc_cell_km.first()
    print(f"wrote {len(df):,} rows, {df.area_id.nunique()} areas -> {OUT_PATH}")
    print("distance to BGC cells (km):", km.describe().round(1).to_dict())


if __name__ == "__main__":
    main()
