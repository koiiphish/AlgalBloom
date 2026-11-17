"""Phase 0 recon: download the Tasmanian ShellMAP harvest area polygons from theLIST.

Run:  uv run python -m pipeline.fetch.recon_tas_boundaries

Source: theLIST Public/MarineAndCoastal MapServer, layer 92 "ShellMAP Harvest Area Boundaries"
(verified 2026-11-17; fields GA_NAME, HA_NAME, AREA_HA; query supports geoJSON).

LICENCE NOT YET CONFIRMED (see docs/data_sources.md). The file is saved to the git-ignored
data/ cache for local research only. Do NOT publish it until theLIST confirms the licence.
"""

from pipeline.config import RAW_DIR
from pipeline.http import get, robots_allows

LAYER_URL = (
    "https://services.thelist.tas.gov.au/arcgis/rest/services/Public/MarineAndCoastal/MapServer/92"
)


def main() -> None:
    """Fetch all features of layer 92 as GeoJSON in WGS84 and save them (a single request)."""
    query_url = f"{LAYER_URL}/query"
    if robots_allows(query_url) is not True:
        raise SystemExit(f"robots.txt does not clearly allow {query_url}; stopping.")
    params = {
        "where": "1=1",
        "outFields": "OBJECTID,GA_NAME,HA_NAME,AREA_HA",
        "outSR": 4326,  # ask the server for lon/lat instead of Web Mercator
        "f": "geojson",
    }
    resp = get(query_url, params=params)
    out = RAW_DIR / "thelist" / "shellmap_harvest_areas.geojson"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(resp.content)
    n = resp.json().get("features", [])
    print(f"saved {len(n)} features -> {out}")
    # The layer's maxRecordCount is 2000; if we ever hit it, results would be truncated.
    if len(n) >= 2000:
        raise SystemExit("Hit maxRecordCount; results truncated. Add paging.")


if __name__ == "__main__":
    main()
