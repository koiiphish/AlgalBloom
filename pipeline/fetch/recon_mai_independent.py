"""Independent satellite chlorophyll at Maria Island (MAI), to test the post-2022 OLCI decline.

OLCI (Copernicus) over Tasmania falls from 2022 while in-situ chl at Maria Island rises
(design note D006 update). This pulls two independent sensors from IMOS for the
same small window used in that comparison:
  - MODIS-Aqua chl_oci, daily, 2019-2024 (one sensor spanning the 2022 boundary)
  - VIIRS-SNPP chl_oci, every 2nd day, 2022 onwards (recent years)
Paths verified by listing the AODN THREDDS catalog on 2026-11-18.

Run:  uv run python -m pipeline.fetch.recon_mai_independent
Output (resumable, one row per day): data/interim/mai_independent_chl.csv
"""

import csv
import time
from datetime import date, timedelta

import numpy as np
import requests
import xarray as xr

from pipeline.config import DATA_DIR
from pipeline.http import get

# THREDDS NetCDF Subset Service: returns only the requested window (~6 KB, ~2 s per day),
# ~8x faster than OPeNDAP here because OPeNDAP re-reads ~300 metadata attributes per file.
NCSS = "https://thredds.aodn.org.au/thredds/ncss/grid/IMOS/SRS/OC/gridded"
MAI_LAT, MAI_LON = -42.5967, 148.2333
HALF_LAT, HALF_LON = 0.03, 0.04  # same window as the OLCI-vs-in-situ comparison
OUT = DATA_DIR / "interim" / "mai_independent_chl.csv"
PAUSE_S = 0.3  # be polite to the AODN server

SENSORS = {
    # name: (folder, file prefix, first day, last day, step in days)
    "modis_aqua": ("aqua", "A", date(2019, 1, 1), date(2024, 12, 31), 1),
    "viirs_snpp": ("snpp", "V", date(2022, 1, 1), date(2026, 11, 10), 2),
}


def url_for(folder: str, prefix: str, d: date) -> str:
    """NCSS URL of one daily chl_oci file."""
    return f"{NCSS}/{folder}/P1D/{d:%Y/%m}/{prefix}.P1D.{d:%Y%m%d}T053000Z.aust.chl_oci.nc"


def window_stats(url: str) -> tuple[float, int]:
    """Median chl and valid-pixel count in the MAI window (values <= 0 treated as missing)."""
    params = {
        "var": "chl_oci",
        "north": MAI_LAT + HALF_LAT,
        "south": MAI_LAT - HALF_LAT,
        "east": MAI_LON + HALF_LON,
        "west": MAI_LON - HALF_LON,
        "accept": "netcdf",
    }
    resp = get(url, params=params)  # raises on HTTP errors (e.g. 404 = no file that day)
    tmp = OUT.parent / "_ncss_tmp.nc"
    tmp.write_bytes(resp.content)
    with xr.open_dataset(tmp, engine="netcdf4") as ds:
        a = ds.chl_oci.values.astype(float)
    a = a[np.isfinite(a) & (a > 0)]
    return (float(np.median(a)) if a.size else float("nan")), int(a.size)


def done_keys() -> set[tuple[str, str]]:
    """(sensor, date) pairs already in the output file, for resuming."""
    if not OUT.exists():
        return set()
    with OUT.open(newline="", encoding="utf-8") as f:
        return {(r["sensor"], r["date"]) for r in csv.DictReader(f)}


def main() -> None:
    """Fetch every sensor/day not yet done and append results as we go."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = done_keys()
    new_file = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        if new_file:
            w.writerow(["sensor", "date", "chl_median", "n_valid", "status"])
        for sensor, (folder, prefix, start, end, step) in SENSORS.items():
            d, n = start, 0
            while d <= end:
                if (sensor, d.isoformat()) not in done:
                    try:
                        med, nv = window_stats(url_for(folder, prefix, d))
                        w.writerow([sensor, d.isoformat(), med, nv, "ok"])
                    except (requests.RequestException, OSError):  # missing day / error
                        w.writerow([sensor, d.isoformat(), "", 0, "missing"])
                    f.flush()
                    time.sleep(PAUSE_S)
                    n += 1
                    if n % 200 == 0:
                        print(f"{sensor}: {n} days fetched, at {d}", flush=True)
                d += timedelta(days=step)
            print(f"{sensor}: finished", flush=True)


if __name__ == "__main__":
    main()
