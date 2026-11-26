"""One-off download of Copernicus OLCI 300 m chlorophyll history for coastal boxes around
the SA and Tasmanian growing areas ("option B" in design note D006/D007).

Why now: the multi-year dataset version 202211 retires on 2026-11-24, and its replacement
(202611) does not support regional subsetting yet. We grab only the coastal boxes we need
(not the whole regional boxes, ~26 GB) as insurance for Phase 2.

Run:  uv run python -m pipeline.fetch.history_olci_300m            # download
      uv run python -m pipeline.fetch.history_olci_300m --dry-run  # size estimate only

Output: data/raw/copernicus/history_olci_300m_v202211/<box>_<year>.nc (one file per box/year,
so an interrupted run can resume with skip_existing).
"""

import argparse
import os
from dataclasses import dataclass

import copernicusmarine
import geopandas as gpd
from dotenv import load_dotenv

from pipeline.config import RAW_DIR, REPO_ROOT, BBox

DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_my_l3-olci-300m_P1D"
DATASET_VERSION = "202211"  # pinned on purpose: see D006
FIRST_DAY, LAST_DAY = "2016-04-25", "2026-11-09"  # full range per describe() on 2026-11-17
YEARS = range(2016, 2027)
OUT_DIR = RAW_DIR / "copernicus" / f"history_olci_300m_v{DATASET_VERSION}"

# SA: PROVISIONAL hand-drawn boxes around the known SA shellfish/aquaculture regions,
# deliberately generous because PIRSA polygons are not available yet. When they arrive,
# check every polygon (+ buffer) falls inside one of these boxes (see check in Phase 2).
SA_BOXES = [
    BBox("sa_west_coast_bays", west=132.8, south=-33.6, east=134.6, north=-31.9),  # Denial-Venus
    BBox("sa_lower_eyre", west=135.0, south=-35.0, east=136.3, north=-34.0),  # Coffin, Lincoln
    BBox("sa_spencer_gulf", west=136.0, south=-34.3, east=138.1, north=-32.5),  # Cowell, upper SG
    BBox("sa_gsv_yorke_ki", west=136.5, south=-36.1, east=138.6, north=-34.3),  # Yorke, GSV, KI
    BBox("sa_coorong", west=138.7, south=-36.2, east=139.5, north=-35.4),  # Murray Mouth / Coorong
    # Added 2026-11-18 (Phase 3): the KAI NRS station (136.447E) lies just west of sa_gsv_yorke_ki
    BBox("sa_kai_station", west=136.25, south=-36.05, east=136.65, north=-35.6),
]  # fmt: skip

TAS_PAD_DEG = 0.15  # ~12-16 km padding around each Tas growing-area cluster


@dataclass(frozen=True)
class Job:
    """One download: a box and a calendar year."""

    box: BBox
    start: str
    end: str


def tas_boxes(pad: float = TAS_PAD_DEG) -> list[BBox]:
    """Build padded boxes around the Tas harvest areas, merging boxes that overlap."""
    areas = gpd.read_file(RAW_DIR / "thelist" / "shellmap_harvest_areas.geojson")
    boxes = [
        [b.minx - pad, b.miny - pad, b.maxx + pad, b.maxy + pad]
        for b in areas.dissolve(by="GA_NAME").bounds.itertuples()
    ]
    merged: list[list[float]] = []
    for b in sorted(boxes):
        for m in merged:
            if b[0] <= m[2] and b[2] >= m[0] and b[1] <= m[3] and b[3] >= m[1]:  # overlap
                m[:] = [min(m[0], b[0]), min(m[1], b[1]), max(m[2], b[2]), max(m[3], b[3])]
                break
        else:
            merged.append(b)
    return [
        BBox(
            f"tas_{i:02d}", west=round(w, 3), south=round(s, 3), east=round(e, 3), north=round(n, 3)
        )
        for i, (w, s, e, n) in enumerate(merged)
    ]


def jobs() -> list[Job]:
    """All (box, year) downloads, clipped to the dataset's time range."""
    out = []
    for box in SA_BOXES + tas_boxes():
        for year in YEARS:
            start = max(f"{year}-01-01", FIRST_DAY)
            end = min(f"{year}-12-31", LAST_DAY)
            out.append(Job(box, start, end))
    return out


def main() -> None:
    """Dry-run (size estimate) or download every job."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="estimate size only")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    creds = {
        "username": os.environ["COPERNICUSMARINE_SERVICE_USERNAME"],
        "password": os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"],
    }
    all_jobs = jobs()
    boxes = {j.box.name: j.box for j in all_jobs}
    area = sum((b.east - b.west) * (b.north - b.south) for b in boxes.values())
    print(f"{len(boxes)} boxes, total {area:.1f} deg^2; {len(all_jobs)} box-year jobs")

    total_mb = 0.0
    for job in all_jobs:
        res = copernicusmarine.subset(
            dataset_id=DATASET_ID,
            dataset_version=DATASET_VERSION,
            variables=["CHL", "CHL_uncertainty", "flags"],
            minimum_longitude=job.box.west,
            maximum_longitude=job.box.east,
            minimum_latitude=job.box.south,
            maximum_latitude=job.box.north,
            start_datetime=job.start,
            end_datetime=job.end,
            output_directory=OUT_DIR,
            output_filename=f"{job.box.name}_{job.start[:4]}.nc",
            netcdf_compression_level=1,  # mostly-NaN arrays compress very well
            skip_existing=True,
            dry_run=args.dry_run,
            disable_progress_bar=True,
            **creds,
        )
        total_mb += res.file_size or 0
        if not args.dry_run:
            print(f"ok {job.box.name} {job.start[:4]}", flush=True)
    label = "estimated uncompressed" if args.dry_run else "reported"
    print(f"Total {label} size: {total_mb / 1024:.1f} GB")


if __name__ == "__main__":
    main()
