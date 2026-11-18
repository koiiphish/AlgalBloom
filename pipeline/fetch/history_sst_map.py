"""One-off download of OSTIA reprocessed SST, 1991-2020, for the whole SA map box (Phase 4).

The SST-anomaly map layer needs a gridded 1991-2020 climatology for both map regions (D014).
Tasmania is already cached (pipeline.fetch.history_ocean covers TAS_BBOX). The earlier SA download
covered only the small NRS-stations box, so this fetches SA_BBOX.

Product: OSTIA reprocessed SST (SST_GLO_SST_L4_REP_OBSERVATIONS_010_011, doi 10.48670/moi-00168),
dataset METOFFICE-GLO-SST-L4-REP-OBS-SST, version 202003, variable analysed_sst (verified with
copernicusmarine.describe, 2026-11-18; see docs/data_sources.md).

Run:  uv run python -m pipeline.fetch.history_sst_map [--dry-run]
"""

import argparse
import os

import copernicusmarine
from dotenv import load_dotenv

from pipeline.config import RAW_DIR, REPO_ROOT, SA_BBOX

DATASET_ID, VERSION = "METOFFICE-GLO-SST-L4-REP-OBS-SST", "202003"
OUT_DIR = RAW_DIR / "copernicus" / "history_sst_map_sa"
CLIM_START, CLIM_END = "1991-01-01", "2020-12-31"


def main() -> None:
    """Download (or dry-run) the SA_BBOX OSTIA reprocessed record for the climatology years."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    res = copernicusmarine.subset(
        dataset_id=DATASET_ID,
        dataset_version=VERSION,
        variables=["analysed_sst"],
        minimum_longitude=SA_BBOX.west,
        maximum_longitude=SA_BBOX.east,
        minimum_latitude=SA_BBOX.south,
        maximum_latitude=SA_BBOX.north,
        start_datetime=CLIM_START,
        end_datetime=CLIM_END,
        output_directory=OUT_DIR,
        output_filename="ostia_rep.nc",
        netcdf_compression_level=1,
        skip_existing=True,
        dry_run=args.dry_run,
        disable_progress_bar=True,
        username=os.environ["COPERNICUSMARINE_SERVICE_USERNAME"],
        password=os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"],
    )
    print(f"{'planned' if args.dry_run else 'ok'}: ~{round(res.file_size or 0)} MB uncompressed")


if __name__ == "__main__":
    main()
