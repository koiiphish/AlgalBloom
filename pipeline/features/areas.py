"""Prediction areas: Tasmanian ShellMAP harvest-area polygons plus a coastal buffer.

Polygons come from theLIST layer 92 (downloaded by pipeline.fetch.recon_tas_boundaries into
the git-ignored data/ folder; licence pending, so they are never published from here).

Buffering is done in metres in GDA94 / MGA zone 55 (EPSG:28355), which covers Tasmania,
then converted back to lon/lat (EPSG:4326) to match the satellite grids.
"""

import geopandas as gpd

from pipeline.config import RAW_DIR
from pipeline.labels.shellmap import make_area_id
from pipeline.labels.tas_lookup import match_key

TAS_POLYGONS = RAW_DIR / "thelist" / "shellmap_harvest_areas.geojson"
METRIC_CRS = 28355  # GDA94 / MGA zone 55 (metres)
DEFAULT_BUFFER_KM = 2.0  # smallest buffer giving every Tas area satellite pixels (Phase 0)


def load_tas_areas() -> gpd.GeoDataFrame:
    """Tas harvest areas with stable IDs, one row per area (multi-part areas dissolved)."""
    gdf = gpd.read_file(TAS_POLYGONS)
    gdf["area_id"] = [make_area_id(g, h) for g, h in zip(gdf.GA_NAME, gdf.HA_NAME, strict=True)]
    gdf = gdf.dissolve(by="area_id", aggfunc={"GA_NAME": "first", "HA_NAME": "first",
                                               "AREA_HA": "sum"}).reset_index()  # fmt: skip
    gdf["match_key"] = gdf["area_id"].map(match_key)  # joins to labels/status_snapshots.csv
    gdf = gdf.rename(
        columns={"GA_NAME": "growing_area", "HA_NAME": "harvest_area", "AREA_HA": "area_ha"}
    )
    return gdf[["area_id", "match_key", "growing_area", "harvest_area", "area_ha", "geometry"]]


def buffer_areas(areas: gpd.GeoDataFrame, km: float = DEFAULT_BUFFER_KM) -> gpd.GeoDataFrame:
    """Return a copy with each polygon grown by `km` kilometres (in a metric CRS)."""
    out = areas.copy()
    out["geometry"] = areas.to_crs(METRIC_CRS).buffer(km * 1000).to_crs(4326)
    out["buffer_km"] = km
    return out
