"""Link ShellMAP notice area names to theLIST harvest-area polygons.

The notice and theLIST spell some names differently (checked on notice 2026/067):
  - the notice says "Zone North" / "Zone GB1" / "Zone 6A/B" where theLIST says
    "North" / "GB1" / "6A/B" (but both say "Zone 1" for others);
  - the notice says "Recherch Bay" where theLIST says "Recherche Bay".
So names are compared through `match_key`, which drops a leading "zone_" and applies
known spelling aliases.

`labels/reference/tas_area_lookup.csv` is built locally from the (git-ignored) theLIST
download and committed. It holds names, IDs and areas only (no geometry), because the
polygon licence is not yet confirmed. The daily archiver uses it to flag new/unknown names.

Run (locally, after pipeline.fetch.recon_tas_boundaries):
    uv run python -m pipeline.labels.tas_lookup
"""

import csv
from pathlib import Path

from pipeline.config import RAW_DIR, REPO_ROOT
from pipeline.labels.shellmap import make_area_id

LOOKUP_PATH = REPO_ROOT / "labels" / "reference" / "tas_area_lookup.csv"
SPELLING_ALIASES = {"recherch_bay": "recherche_bay"}  # notice spelling -> theLIST spelling

# Notice areas known to have no theLIST polygon (checked 2026-11-17), so they are not
# reported as "new/unknown" every day. Barnes Bay is a wild-harvest nursery/source area.
KNOWN_WITHOUT_POLYGON = {"tas:barnes_bay:barnes_bay"}


def match_key(area_id: str) -> str:
    """Normalise an area_id so notice and theLIST spellings of the same area compare equal."""
    region, growing, harvest = area_id.split(":", 2)
    growing = SPELLING_ALIASES.get(growing, growing)
    harvest = SPELLING_ALIASES.get(harvest, harvest)
    harvest = harvest.removeprefix("zone_")
    return f"{region}:{growing}:{harvest}"


def load_lookup(path: Path = LOOKUP_PATH) -> dict[str, dict[str, str]]:
    """Load the committed lookup as {match_key: row}."""
    with path.open(newline="", encoding="utf-8") as f:
        return {row["match_key"]: row for row in csv.DictReader(f)}


def build_lookup() -> list[dict[str, str]]:
    """Build lookup rows from the local theLIST GeoJSON (needs geopandas + the data file)."""
    import geopandas as gpd  # local-only dependency path; not needed by the daily job

    gdf = gpd.read_file(RAW_DIR / "thelist" / "shellmap_harvest_areas.geojson")
    rows = []
    for r in gdf.sort_values(["GA_NAME", "HA_NAME"]).itertuples():
        list_id = make_area_id(r.GA_NAME, r.HA_NAME)
        rows.append(
            {
                "match_key": match_key(list_id),
                "list_area_id": list_id,
                "list_growing_area": r.GA_NAME,
                "list_harvest_area": r.HA_NAME,
                "list_objectid": str(r.OBJECTID),
                "area_ha": f"{r.AREA_HA:.1f}",
            }
        )
    return rows


def main() -> None:
    """Write labels/reference/tas_area_lookup.csv."""
    rows = build_lookup()
    LOOKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOOKUP_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows -> {LOOKUP_PATH}")


if __name__ == "__main__":
    main()
