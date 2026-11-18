"""Per-area daily chlorophyll-a from the OLCI 300 m history (area x day table).

For each area, every 300 m pixel whose centre falls inside the buffered polygon is used.
Per day we keep the median chl of the valid pixels and how many pixels were valid, so cloud
gaps are explicit (`n_valid`) instead of silently filled.

We also keep a "core" median (`chl_core`, `n_core`) that leaves out cloud-edge pixels: valid
pixels touching (8-neighbourhood) an invalid pixel that is not land. Over Tasmania, cloud-edge
pixels read ~29% higher than interior ones (cloud adjacency / stray light), and they are 18% of
valid pixels (D011 update). Land comes from the product's `flags` (its only flag is LAND),
so pixels next to the coast are not mistaken for cloud edges.

Run:  uv run python -m pipeline.features.chl
Output: data/interim/chl_area_day_<version>.parquet
"""

import glob
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import xarray as xr

from pipeline.config import DATA_DIR, RAW_DIR
from pipeline.features.areas import buffer_areas, load_tas_areas

HISTORY_VERSION = "202211"
HISTORY_DIR = RAW_DIR / "copernicus" / f"history_olci_300m_v{HISTORY_VERSION}"
OUT_PATH = DATA_DIR / "interim" / f"chl_area_day_v{HISTORY_VERSION}.parquet"


def pixel_mask(lat: np.ndarray, lon: np.ndarray, geom: shapely.Geometry) -> np.ndarray:
    """Boolean (lat, lon) mask of grid cells whose centre lies inside `geom`."""
    lon2d, lat2d = np.meshgrid(lon, lat)
    return shapely.contains_xy(geom, lon2d, lat2d)


def cloud_edge(valid: np.ndarray, land: np.ndarray) -> np.ndarray:
    """(time, lat, lon) True for valid pixels with an invalid, non-land 8-neighbour.

    Pixels outside the downloaded box count as not invalid (no edge is invented there).
    """
    gap = ~valid & ~land[None, :, :]
    p = np.pad(gap, ((0, 0), (1, 1), (1, 1)))
    ny, nx = gap.shape[1], gap.shape[2]
    near = np.zeros_like(gap)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            near |= p[:, dy : dy + ny, dx : dx + nx]
    return valid & near


def _median_and_count(pix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-row median of finite values and their count (NaN median where count is 0)."""
    n = np.isfinite(pix).sum(axis=1)
    with np.errstate(all="ignore"):
        med = np.nanmedian(np.where(n[:, None] > 0, pix, 0.0), axis=1)
    return np.where(n > 0, med, np.nan), n


def area_daily_stats(
    chl: np.ndarray, mask: np.ndarray, edge: np.ndarray | None = None
) -> pd.DataFrame:
    """Median chl and valid-pixel count per day for one area (plus the cloud-edge-free
    "core" median and count when an `edge` array is given).

    `chl` is (time, lat, lon); invalid values (NaN, <= 0) are ignored.
    """
    pix = chl[:, mask]  # (time, n_pixels in area)
    pix = np.where(pix > 0, pix, np.nan)
    median, n_valid = _median_and_count(pix)
    out = pd.DataFrame({"chl": median, "n_valid": n_valid, "n_pixels": mask.sum()})
    if edge is not None:
        core, n_core = _median_and_count(np.where(edge[:, mask], np.nan, pix))
        out["chl_core"], out["n_core"] = core, n_core
    return out


def extract_file(path: Path, areas: gpd.GeoDataFrame) -> pd.DataFrame:
    """Daily stats for every area whose buffered polygon is fully covered by this file's box."""
    with xr.open_dataset(path) as ds:
        lat, lon = ds.latitude.values, ds.longitude.values
        box = shapely.box(lon.min(), lat.min(), lon.max(), lat.max())
        inside = areas[areas.geometry.within(box)]
        if inside.empty:
            return pd.DataFrame()
        chl = ds.CHL.values  # (time, lat, lon), loaded once per file
        land = (ds.flags.values == 1).any(axis=0)  # LAND is static; any day marks it
        dates = pd.to_datetime(ds.time.values).normalize()
    edge = cloud_edge(np.isfinite(chl) & (chl > 0), land)
    parts = []
    for row in inside.itertuples():
        stats = area_daily_stats(chl, pixel_mask(lat, lon, row.geometry), edge)
        stats.insert(0, "date", dates)
        stats.insert(0, "area_id", row.area_id)
        parts.append(stats)
    return pd.concat(parts, ignore_index=True)


def build(history_dir: Path = HISTORY_DIR) -> pd.DataFrame:
    """Area x day chl table for all Tas areas and all downloaded years."""
    areas = buffer_areas(load_tas_areas())
    files = sorted(glob.glob(str(history_dir / "tas_*.nc")))
    df = pd.concat([extract_file(Path(f), areas) for f in files], ignore_index=True)
    # An area can sit in two overlapping boxes: keep the copy with more valid pixels.
    df = df.sort_values("n_valid").drop_duplicates(["area_id", "date"], keep="last")
    missing = set(areas.area_id) - set(df.area_id)
    if missing:
        raise ValueError(f"Areas not fully inside any downloaded box: {sorted(missing)}")
    df["processing"] = np.where(df.date < "2022-01-01", "my", "myint")  # see D006 update
    return df.sort_values(["area_id", "date"]).reset_index(drop=True)


def main() -> None:
    """Build and save the table, then print a short coverage summary."""
    df = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(f"wrote {len(df):,} rows ({df.area_id.nunique()} areas) -> {OUT_PATH}")
    print("share of area-days with >=1 valid pixel:", round((df.n_valid > 0).mean(), 3))
    print(df.groupby("area_id").n_pixels.first().describe().round(1).to_string())


if __name__ == "__main__":
    main()
