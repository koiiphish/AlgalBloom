"""Compare Copernicus OLCI 300 m chlorophyll between dataset versions 202211 and 202611.

Why: version 202211 (our downloaded history) switches from fully reprocessed ("my") to
interim ("myint") processing on 2022-01-01, and over Tasmania it drifts away from in-situ
chlorophyll after that date (design note D006 update). If the new full reprocessing
(202611) agrees with 202211 before 2022 but not after, the interim processing is the cause.

Version 202611 has no subsetting service yet, so this downloads WHOLE global daily files
(~2.7 GB each), crops them to our Tasmanian boxes, and deletes the global file.

Run:  uv run python -m pipeline.fetch.recon_version_check
"""

import glob
import os
from pathlib import Path

import copernicusmarine
import numpy as np
import pandas as pd
import xarray as xr
from dotenv import load_dotenv

from pipeline.config import RAW_DIR, REPO_ROOT
from pipeline.fetch.history_olci_300m import tas_boxes
from pipeline.fetch.opendap import subset_bbox

DATASET_ID = "cmems_obs-oc_glo_bgc-plankton_my_l3-olci-300m_P1D"
OLD_DIR = RAW_DIR / "copernicus" / "history_olci_300m_v202211"
OUT_DIR = RAW_DIR / "copernicus" / "version_check_202611"
# Clearest late-January days over Tasmania in each processing era (chosen from 202211 counts).
DAYS = ["2019-01-21", "2024-01-30"]


def download_and_crop(day: str) -> dict[str, Path]:
    """Download one global 202611 file, crop to each Tas box (one file per box), delete it.

    Original files name their coordinates lat/lon (the subset service says latitude/
    longitude), so they are renamed to match our history files.
    """
    outs = {b.name: OUT_DIR / f"{day}_{b.name}.nc" for b in tas_boxes()}
    if all(p.exists() for p in outs.values()):
        return outs
    tmp = OUT_DIR / "tmp"
    existing = sorted(tmp.glob(f"{day.replace('-', '')}_*.nc"))
    if existing:  # reuse a file left by an interrupted run
        global_file = existing[0]
    else:
        load_dotenv(REPO_ROOT / ".env")
        res = copernicusmarine.get(
            dataset_id=DATASET_ID,
            dataset_version="202611",
            filter=f"*{day.replace('-', '')}*",
            output_directory=tmp,
            no_directories=True,
            username=os.environ["COPERNICUSMARINE_SERVICE_USERNAME"],
            password=os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"],
            disable_progress_bar=True,
        )
        global_file = Path(res.files[0].file_path)
    with xr.open_dataset(global_file) as ds:
        ds = ds[["CHL"]].rename({"lat": "latitude", "lon": "longitude"})
        for b in tas_boxes():
            subset_bbox(ds, b, "latitude", "longitude").load().to_netcdf(outs[b.name])
    global_file.unlink()  # keep only the small crops
    return outs


def old_values(day: str) -> dict[str, xr.DataArray]:
    """The same day from our 202211 history, per Tas box."""
    year = day[:4]
    out = {}
    for f in sorted(glob.glob(str(OLD_DIR / f"tas_*_{year}.nc"))):
        box = Path(f).stem.rsplit("_", 1)[0]
        with xr.open_dataset(f) as ds:
            out[box] = ds.CHL.sel(time=day).load()
    return out


def compare(day: str) -> pd.Series:
    """Pixel-matched comparison of log10 chl (new minus old) over all Tas boxes for one day."""
    crops = download_and_crop(day)
    old = old_values(day)
    diffs = []
    for b in tas_boxes():
        o = old[b.name].squeeze(drop=True)
        with xr.open_dataset(crops[b.name]) as nds:
            new = nds.CHL.squeeze(drop=True).load()
        # Match each old pixel to the nearest new pixel within half a 300 m pixel.
        new_on_old = new.reindex_like(o, method="nearest", tolerance=1 / 360)
        ok = (new_on_old > 0) & (o > 0)
        diffs.append(np.log10(new_on_old.where(ok)) - np.log10(o.where(ok)))
    d = np.concatenate([x.values.ravel() for x in diffs])
    d = d[np.isfinite(d)]
    return pd.Series(
        {
            "matched_pixels": d.size,
            "median_log10_diff_new_minus_old": round(float(np.median(d)), 3),
            "median_ratio_new_over_old": round(float(10 ** np.median(d)), 3),
            "p10": round(float(np.percentile(d, 10)), 3),
            "p90": round(float(np.percentile(d, 90)), 3),
        },
        name=day,
    )


def main() -> None:
    """Run the comparison for each day and print a table."""
    print(pd.DataFrame([compare(day) for day in DAYS]).to_string())


if __name__ == "__main__":
    main()
