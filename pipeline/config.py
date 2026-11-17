"""Shared configuration for the pipeline: paths, regions, test window and HTTP identity.

Phase 0 note: the SA harvest-area polygons are not available yet (see docs/data_sources.md),
so the recon scripts use rectangular bounding boxes for each region instead.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

# --- Paths -------------------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"  # git-ignored cache for raw and interim downloads
RAW_DIR = DATA_DIR / "raw"

# --- HTTP identity -----------------------------------------------------------------------------
# A descriptive User-Agent so data providers can see who is calling and why.
# TODO(Phase 1): add the public GitHub repo URL once it exists.
USER_AGENT = "hab-forecaster/0.1 (non-commercial research; coastal harmful algal bloom forecasting)"
REQUEST_TIMEOUT_S = 60


@dataclass(frozen=True)
class BBox:
    """A lon/lat bounding box in WGS84 (EPSG:4326)."""

    name: str
    west: float
    south: float
    east: float
    north: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        """Return (west, south, east, north)."""
        return (self.west, self.south, self.east, self.north)


# Regional boxes covering the SA gulfs/KI/Eyre Peninsula and the Tasmanian coast.
# Deliberately generous; they get replaced by harvest-area polygons + coastal buffers later.
SA_BBOX = BBox("south_australia", west=132.0, south=-36.5, east=139.0, north=-32.0)
TAS_BBOX = BBox("tasmania", west=144.0, south=-44.0, east=149.0, north=-39.5)
REGIONS = (SA_BBOX, TAS_BBOX)


@dataclass(frozen=True)
class TestPoint:
    """A single coastal point used for point-based APIs (e.g. weather) during recon."""

    name: str
    lat: float
    lon: float


# One representative aquaculture location per state, for point APIs (weather).
# Coffin Bay (SA oyster growing area) and the Huon estuary (Tas salmon/shellfish).
SA_POINT = TestPoint("coffin_bay", lat=-34.62, lon=135.47)
TAS_POINT = TestPoint("huon_estuary", lat=-43.23, lon=147.08)
TEST_POINTS = (SA_POINT, TAS_POINT)

# --- Recon test window -------------------------------------------------------------------------
# One recent week. Fixed (not "today") so recon runs are reproducible.
RECON_START = date(2026, 11, 1)
RECON_END = date(2026, 11, 7)
