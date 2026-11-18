"""Download the daily inputs (Phase 4). Every failure is raised as InputError so the daily job
can fall back to yesterday's output and mark it stale, instead of publishing a partial result.

Datasets (IDs and versions verified 2026-11-18, docs/data_sources.md):
  - OLCI 300 m near-real-time chl, cmems_obs-oc_glo_bgc-plankton_nrt_l3-olci-300m_P1D, version
    202207 (retires 2027-01-12: pinned so the switch is a deliberate, checked change; D014).
    Rolling ~18-day archive, newest day ~2 days old. Matches our training history over
    1-7 Nov 2026 (median area ratio 1.000; D014).
  - OSTIA near-real-time SST, METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2 (default version), newest day
    ~1 day old.
"""

import os
from pathlib import Path

import copernicusmarine
from dotenv import load_dotenv

from pipeline.config import RAW_DIR, REPO_ROOT, BBox
from pipeline.features.areas import TAS_POLYGONS

CHL_DATASET, CHL_VERSION = "cmems_obs-oc_glo_bgc-plankton_nrt_l3-olci-300m_P1D", "202207"
SST_DATASET = "METOFFICE-GLO-SST-L4-NRT-OBS-SST-V2"


class InputError(RuntimeError):
    """An input could not be fetched or is unusable."""


def _credentials() -> dict[str, str]:
    """Copernicus Marine login from the environment (GitHub secret, or the local .env)."""
    load_dotenv(REPO_ROOT / ".env")
    try:
        return {
            "username": os.environ["COPERNICUSMARINE_SERVICE_USERNAME"],
            "password": os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"],
        }
    except KeyError as e:
        raise InputError(f"missing Copernicus credential {e.args[0]} (never printed)") from None


def _subset(dataset_id: str, version: str | None, variables: list[str], box: BBox,
            start: str, end: str, out_dir: Path, name: str) -> Path:  # fmt: skip
    """One copernicusmarine subset request; any failure becomes an InputError."""
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        copernicusmarine.subset(
            dataset_id=dataset_id,
            dataset_version=version,
            variables=variables,
            minimum_longitude=box.west,
            maximum_longitude=box.east,
            minimum_latitude=box.south,
            maximum_latitude=box.north,
            start_datetime=start,
            end_datetime=end,
            output_directory=out_dir,
            output_filename=name,
            netcdf_compression_level=1,
            overwrite=True,
            disable_progress_bar=True,
            **_credentials(),
        )
    except InputError:
        raise
    except Exception as e:  # the toolbox raises many types; the message is what matters
        raise InputError(f"{dataset_id} {box.name}: {type(e).__name__}: {e}") from e
    path = out_dir / name
    if not path.exists():
        raise InputError(f"{dataset_id} {box.name}: no file written")
    return path


def fetch_chl(box: BBox, start: str, end: str, out_dir: Path, with_flags: bool = True) -> Path:
    """Near-real-time OLCI 300 m chl (+ flags, which the area extraction needs for land)."""
    variables = ["CHL", "flags"] if with_flags else ["CHL"]
    return _subset(CHL_DATASET, CHL_VERSION, variables, box, start, end, out_dir,
                   f"chl_{box.name}.nc")  # fmt: skip


def fetch_sst(box: BBox, start: str, end: str, out_dir: Path) -> Path:
    """Near-real-time OSTIA SST for a box."""
    return _subset(SST_DATASET, None, ["analysed_sst"], box, start, end, out_dir,
                   f"sst_{box.name}.nc")  # fmt: skip


def ensure_tas_polygons() -> Path:
    """Make sure the theLIST polygons are in the git-ignored cache (one request if missing).

    In GitHub Actions the cache folder is restored by actions/cache with a weekly key, so this
    sends at most one request a week. The polygons are used only to choose satellite pixels;
    they are never published until theLIST confirms the licence (decision A, D014).
    """
    if not TAS_POLYGONS.exists():
        from pipeline.fetch import recon_tas_boundaries

        try:
            recon_tas_boundaries.main()
        except (Exception, SystemExit) as e:
            raise InputError(f"theLIST harvest-area polygons: {e}") from e
    return TAS_POLYGONS


DOWNLOAD_DIR = RAW_DIR / "daily"
