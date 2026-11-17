"""Phase 0 recon: pull small SA + Tasmania subsets from Copernicus Marine.

Run:  uv run python -m pipeline.fetch.recon_copernicus

Dataset IDs, variable names and time ranges were all taken from the live catalogue with
`copernicusmarine.describe(dataset_id=...)` on 2026-11-17 (toolbox 2.5.1).

Observations use the recon week (1-7 Nov 2026), so they are directly comparable to IMOS.
Forecasts use "today + 7 days" because that is what the daily pipeline will consume.
Credentials come from `.env` (never printed or logged).
"""

import os
from datetime import date, timedelta

import copernicusmarine
from dotenv import load_dotenv

from pipeline.config import RAW_DIR, RECON_END, RECON_START, REGIONS, REPO_ROOT

TODAY = date(2026, 11, 17)  # fixed for reproducibility of this recon run
FORECAST_END = TODAY + timedelta(days=7)

# (short name, dataset_id, variables, start, end, surface_only)
REQUESTS = [
    # Observed chlorophyll, near-real-time (NRT) rolling archive
    ("chl_nrt_olci_300m", "cmems_obs-oc_glo_bgc-plankton_nrt_l3-olci-300m_P1D",
     ["CHL", "flags"], RECON_START, RECON_END, False),
    ("chl_nrt_multi_4km", "cmems_obs-oc_glo_bgc-plankton_nrt_l3-multi-4km_P1D",
     ["CHL"], RECON_START, RECON_END, False),
    ("chl_nrt_l4_gapfree_4km", "cmems_obs-oc_glo_bgc-plankton_nrt_l4-gapfree-multi-4km_P1D",
     ["CHL"], RECON_START, RECON_END, False),
    # Modelled chlorophyll analysis + forecast (baseline 3), surface level only
    ("bgc_chl_forecast", "cmems_mod_glo_bgc-pft_anfc_0.25deg_P1D-m",
     ["chl"], TODAY, FORECAST_END, True),
    # Physics analysis + forecast: SST (surface thetao), mixed layer depth, currents
    ("phy_thetao_forecast", "cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m",
     ["thetao"], TODAY, FORECAST_END, True),
    ("phy_2d_forecast", "cmems_mod_glo_phy_anfc_0.083deg_P1D-m",
     ["mlotst"], TODAY, FORECAST_END, False),
    ("phy_cur_forecast", "cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m",
     ["uo", "vo"], TODAY, FORECAST_END, True),
]  # fmt: skip


def main() -> None:
    """Run every request for every region; save NetCDF under data/raw/copernicus/."""
    load_dotenv(REPO_ROOT / ".env")
    user = os.environ["COPERNICUSMARINE_SERVICE_USERNAME"]
    pwd = os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"]
    for name, dataset_id, variables, start, end, surface_only in REQUESTS:
        for region in REGIONS:
            out_dir = RAW_DIR / "copernicus" / name
            out_file = f"{region.name}_{start:%Y%m%d}_{end:%Y%m%d}.nc"
            depth = {"minimum_depth": 0, "maximum_depth": 1} if surface_only else {}
            copernicusmarine.subset(
                dataset_id=dataset_id,
                username=user,
                password=pwd,
                variables=variables,
                minimum_longitude=region.west,
                maximum_longitude=region.east,
                minimum_latitude=region.south,
                maximum_latitude=region.north,
                start_datetime=f"{start:%Y-%m-%d}T00:00:00",
                end_datetime=f"{end:%Y-%m-%d}T23:59:59",
                output_directory=out_dir,
                output_filename=out_file,
                skip_existing=True,
                disable_progress_bar=True,
                **depth,
            )
            print(f"ok {name:24s} {region.name}")


if __name__ == "__main__":
    main()
