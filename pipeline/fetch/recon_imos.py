"""Phase 0 recon: pull one week of IMOS ocean colour (VIIRS chlorophyll-a) and SST
for the SA and Tasmania bounding boxes, via AODN THREDDS/OPeNDAP.

Run:  uv run python -m pipeline.fetch.recon_imos

Products (paths verified by listing the THREDDS catalog on 2026-11-17):
- Chlorophyll-a, VIIRS NOAA-20 and SNPP, daily, OCI algorithm (0.01 deg grid):
    IMOS/SRS/OC/gridded/{noaa20,snpp}/P1D/YYYY/MM/{J,V}.P1D.YYYYMMDDT053000Z.aust.chl_oci.nc
- SST, multi-sensor L3S, day+night, foundation SST (0.02 deg grid):
    IMOS/SRS/SST/ghrsst/L3SM-1d/dn/YYYY/YYYYMMDD092000-ABOM-L3S_GHRSST-SSTfnd-MultiSensor-1d_dn.nc
- SST, RAMSSA L4 gap-free analysis (~9 km grid):
    IMOS/SRS/SST/ghrsst/L4/RAMSSA/YYYY/YYYYMMDD120000-ABOM-L4_GHRSST-SSTfnd-RAMSSA_09km-AUS-v02.0-fv01.0.nc
"""

import time
from collections.abc import Callable
from datetime import date, timedelta

from pipeline.config import RAW_DIR, RECON_END, RECON_START, REGIONS
from pipeline.fetch.opendap import fetch_subset

DODS = "https://thredds.aodn.org.au/thredds/dodsC/"
PAUSE_S = 1.0  # be polite to the AODN server between requests

# Each product: (name, url builder for a date, variables, lat name, lon name)
PRODUCTS: list[tuple[str, Callable[[date], str], list[str], str, str]] = [
    (
        "oc_noaa20_chl_oci",
        lambda d: (
            f"{DODS}IMOS/SRS/OC/gridded/noaa20/P1D/{d:%Y/%m}/J.P1D.{d:%Y%m%d}T053000Z.aust.chl_oci.nc"
        ),  # noqa: E501 (verified URL template)
        ["chl_oci"],
        "latitude",
        "longitude",
    ),
    (
        "oc_snpp_chl_oci",
        lambda d: (
            f"{DODS}IMOS/SRS/OC/gridded/snpp/P1D/{d:%Y/%m}/V.P1D.{d:%Y%m%d}T053000Z.aust.chl_oci.nc"
        ),  # noqa: E501 (verified URL template)
        ["chl_oci"],
        "latitude",
        "longitude",
    ),
    (
        "sst_l3sm_1d_dn",
        lambda d: (
            f"{DODS}IMOS/SRS/SST/ghrsst/L3SM-1d/dn/{d:%Y}/{d:%Y%m%d}092000-ABOM-L3S_GHRSST-SSTfnd-MultiSensor-1d_dn.nc"
        ),  # noqa: E501 (verified URL template)
        ["sea_surface_temperature", "quality_level"],
        "lat",
        "lon",
    ),
    (
        "sst_ramssa_l4",
        lambda d: (
            f"{DODS}IMOS/SRS/SST/ghrsst/L4/RAMSSA/{d:%Y}/{d:%Y%m%d}120000-ABOM-L4_GHRSST-SSTfnd-RAMSSA_09km-AUS-v02.0-fv01.0.nc"
        ),  # noqa: E501 (verified URL template)
        ["analysed_sst", "analysis_error"],
        "lat",
        "lon",
    ),
]


def daterange(start: date, end: date) -> list[date]:
    """All dates from start to end inclusive."""
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def main() -> None:
    """Download each product/day/region subset and print a one-line result for each."""
    for name, url_for, variables, lat_name, lon_name in PRODUCTS:
        for d in daterange(RECON_START, RECON_END):
            url = url_for(d)
            for region in REGIONS:
                out = RAW_DIR / "imos" / name / region.name / f"{d:%Y%m%d}.nc"
                try:
                    fetch_subset(url, variables, region, out, lat_name, lon_name)
                    print(f"ok      {name} {d} {region.name}")
                except OSError as err:  # missing file on the server raises OSError
                    print(f"MISSING {name} {d} {region.name}: {type(err).__name__}")
            time.sleep(PAUSE_S)


if __name__ == "__main__":
    main()
