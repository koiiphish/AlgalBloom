"""One-off download of SST and ocean-model history for the Tasmania box (Phase 2 features).

Products (IDs, versions, variables and time ranges from copernicusmarine.describe, 2026-11-18):
  - OSTIA reprocessed SST, 0.05 deg, 1981-10 -> 2026-06 (SST_GLO_SST_L4_REP_OBSERVATIONS_010_011,
    doi 10.48670/moi-00168): history + 1991-2020 climatology for anomalies / marine heatwaves
  - OSTIA near-real-time SST, 0.05 deg, 2024-01 -> now (SST_GLO_SST_L4_NRT_OBSERVATIONS_010_001,
    doi 10.48670/moi-00165): recent months + overlap to check consistency with REP
  - GLORYS12 reanalysis, 1/12 deg, 1993 -> 2026-10 (GLOBAL_MULTIYEAR_PHY_001_030,
    doi 10.48670/moi-00021): mixed-layer depth and surface currents for all training years;
    same grid/model family as the operational analysis-forecast used in Phase 4

Run:  uv run python -m pipeline.fetch.history_ocean [--region tas|sa] [--dry-run]
"""

import argparse
import os

import copernicusmarine
from dotenv import load_dotenv

from pipeline.config import RAW_DIR, REPO_ROOT, SA_STATIONS_BBOX, TAS_BBOX

BOXES = {"tas": TAS_BBOX, "sa": SA_STATIONS_BBOX}


def out_dir(region: str):
    """Output folder per region, e.g. data/raw/copernicus/history_ocean_tas."""
    return RAW_DIR / "copernicus" / f"history_ocean_{region}"


# (name, dataset_id, version, variables, start, end, surface_only)
REQUESTS = [
    ("ostia_rep", "METOFFICE-GLO-SST-L4-REP-OBS-SST", "202003", ["analysed_sst"],
     "1991-01-01", "2026-06-30", False),
    ("ostia_nrt", "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2", None, ["analysed_sst"],
     "2024-01-17", "2026-11-17", False),
    ("glorys_2d", "cmems_mod_glo_phy_my_0.083deg_P1D-m", "202311", ["mlotst"],
     "2016-01-01", "2026-10-06", False),
    ("glorys_surface", "cmems_mod_glo_phy_my_0.083deg_P1D-m", "202311", ["uo", "vo", "thetao"],
     "2016-01-01", "2026-10-06", True),
]  # fmt: skip


def main() -> None:
    """Download (or dry-run) every request for one region's box."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--region", choices=sorted(BOXES), default="tas")
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    creds = {
        "username": os.environ["COPERNICUSMARINE_SERVICE_USERNAME"],
        "password": os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"],
    }
    b = BOXES[args.region]
    total = 0.0
    for name, dataset_id, version, variables, start, end, surface_only in REQUESTS:
        depth = {"minimum_depth": 0, "maximum_depth": 1} if surface_only else {}
        res = copernicusmarine.subset(
            dataset_id=dataset_id,
            dataset_version=version,
            variables=variables,
            minimum_longitude=b.west,
            maximum_longitude=b.east,
            minimum_latitude=b.south,
            maximum_latitude=b.north,
            start_datetime=start,
            end_datetime=end,
            output_directory=out_dir(args.region),
            output_filename=f"{name}.nc",
            netcdf_compression_level=1,
            skip_existing=True,
            dry_run=args.dry_run,
            disable_progress_bar=True,
            **depth,
            **creds,
        )
        total += res.file_size or 0
        print(f"{'planned' if args.dry_run else 'ok'} {name}: {round(res.file_size or 0)} MB")
    print(f"total {'estimated ' if args.dry_run else ''}{total / 1024:.2f} GB (uncompressed)")


if __name__ == "__main__":
    main()
