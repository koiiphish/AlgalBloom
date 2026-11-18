"""Download Copernicus global biogeochemistry (BGC) model chlorophyll for baseline 3.

Product: GLOBAL_MULTIYEAR_BGC_001_029, dataset `cmems_mod_glo_bgc_my_0.25deg_P1D-m`,
version 202406, variable `chl` (mg m-3), 0.25 deg, daily, 1993-01-01 -> 2026-09-30
(copernicusmarine.describe, 2026-11-18). Surface layer only (top depth level, ~0.5 m).

Why the hindcast and not the analysis-forecast (D012): the analysis-forecast dataset
(`cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m`) has a single "default" part, a best-estimate
time series from 2021-11, and no archive of the forecasts actually issued. Neither
dataset can reproduce issued 1-7 day forecasts, so baseline 3 uses the model's own
best estimate for t+1..t+7, i.e. a "perfect forecast" that flatters the baseline. The hindcast
covers the training years too, so its climatology and threshold can be computed exactly
like our target's (training years only), from one consistent model run.

Run:  uv run python -m pipeline.fetch.history_bgc [--dry-run]
Output: data/raw/copernicus/history_bgc/{tas,sa}_bgc_chl.nc
"""

import argparse
import os

import copernicusmarine
from dotenv import load_dotenv

from pipeline.config import RAW_DIR, REPO_ROOT, SA_STATIONS_BBOX, TAS_BBOX

DATASET_ID = "cmems_mod_glo_bgc_my_0.25deg_P1D-m"
DATASET_VERSION = "202406"
START, END = "2016-01-01", "2026-09-30"
OUT_DIR = RAW_DIR / "copernicus" / "history_bgc"
BOXES = {"tas": TAS_BBOX, "sa": SA_STATIONS_BBOX}


def main() -> None:
    """Download (or dry-run) surface chl for the Tas box and the SA station box."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_dotenv(REPO_ROOT / ".env")
    creds = {
        "username": os.environ["COPERNICUSMARINE_SERVICE_USERNAME"],
        "password": os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"],
    }
    for region, b in BOXES.items():
        # The 0.25 deg grid barely reaches the coast, so pad the box by 0.5 deg
        # to be sure each area has ocean cells nearby (nearest-cell matching, D010).
        res = copernicusmarine.subset(
            dataset_id=DATASET_ID,
            dataset_version=DATASET_VERSION,
            variables=["chl"],
            minimum_longitude=b.west - 0.5,
            maximum_longitude=b.east + 0.5,
            minimum_latitude=b.south - 0.5,
            maximum_latitude=b.north + 0.5,
            minimum_depth=0,
            maximum_depth=1,
            start_datetime=START,
            end_datetime=END,
            output_directory=OUT_DIR,
            output_filename=f"{region}_bgc_chl.nc",
            netcdf_compression_level=1,
            skip_existing=True,
            dry_run=args.dry_run,
            disable_progress_bar=True,
            **creds,
        )
        print(f"{'planned' if args.dry_run else 'ok'} {region}: {round(res.file_size or 0)} MB")


if __name__ == "__main__":
    main()
