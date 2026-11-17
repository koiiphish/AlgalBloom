"""Build labels/events.csv: dated harmful-taxon exceedances at IMOS reference stations.

Run (locally; inputs are manual AODN downloads in the git-ignored data/ folder):
    uv run python -m pipeline.labels.events

Inputs (see docs/data_sources.md, "Manual AODN downloads"):
  - nrs_phyto_genus_*.csv   genus totals (Karenia, Alexandrium, Pseudo-nitzschia, Dinophysis)
  - nrs_phyto_species_*.csv species counts (Gymnodinium catenatum only: the genus
                            Gymnodinium contains non-toxic species)

One row per (sample, taxon) where cells/L >= the lab-alert action level
(pipeline/labels/action_levels.py). Stations outside SA/Tas (e.g. Bonney Coast VBM, Vic)
are excluded. Every row records its source file and the sample's TripCode.
"""

import glob
from pathlib import Path

import pandas as pd

from pipeline.config import RAW_DIR, REPO_ROOT
from pipeline.labels.action_levels import (
    EVENT_LEVELS,
    KARENIA_GROUP_LEVEL,
    PALT_SOURCE,
    ActionLevel,
)

AODN_DIR = RAW_DIR / "aodn_manual"
EVENTS_PATH = REPO_ROOT / "labels" / "events.csv"
STATION_REGION = {
    "MAI": "tas",
    "KAI": "sa",
    "KAID1": "sa",
    "KAID2": "sa",
    "KAID3": "sa",
    "GSV": "sa",
    "USG": "sa",
}  # VBM (Bonney Coast, Victoria) deliberately excluded
META_COLUMNS = ["StationCode", "StationName", "Latitude", "Longitude", "TripCode",
                "SampleTime_Local", "SampleDepth_m"]  # fmt: skip
EVENT_COLUMNS = [
    "date", "region", "station_code", "station_name", "lat", "lon", "sample_depth_m",
    "taxon", "toxin", "cells_per_L", "lab_alert_cells_per_L", "closure_cells_per_L",
    "exceeds_closure_level", "level_basis", "karenia_group_level_exceeded",
    "source_dataset", "source_file", "trip_code", "provenance",
]  # fmt: skip


def latest(pattern: str) -> Path:
    """Most recent file matching a glob in the manual-download folder."""
    matches = sorted(glob.glob(str(AODN_DIR / pattern)))
    if not matches:
        raise FileNotFoundError(f"No file matching {pattern} in {AODN_DIR}")
    return Path(matches[-1])


def exceedances(
    df: pd.DataFrame, column: str, level: ActionLevel, source_file: str
) -> pd.DataFrame:
    """Rows of a wide NRS table where `column` >= the level's lab-alert threshold."""
    counts = pd.to_numeric(df[column], errors="coerce").fillna(0)
    hit = df[(counts >= level.lab_alert) & df["StationCode"].isin(STATION_REGION)].copy()
    hit_counts = counts[hit.index]
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(hit["SampleTime_Local"], format="ISO8601").dt.date.astype(str),
            "region": hit["StationCode"].map(STATION_REGION),
            "station_code": hit["StationCode"],
            "station_name": hit["StationName"],
            "lat": hit["Latitude"],
            "lon": hit["Longitude"],
            "sample_depth_m": hit["SampleDepth_m"],
            "taxon": level.taxon,
            "toxin": level.toxin,
            "cells_per_L": hit_counts.round(1),
            "lab_alert_cells_per_L": level.lab_alert,
            "closure_cells_per_L": level.closure,
            "exceeds_closure_level": (
                hit_counts >= level.closure if level.closure is not None else False
            ),
            "level_basis": f"{level.basis} [{PALT_SOURCE}]",
            "karenia_group_level_exceeded": (
                hit_counts >= KARENIA_GROUP_LEVEL.lab_alert if level.taxon == "Karenia" else ""
            ),
            "source_dataset": "IMOS - Phytoplankton Abundance and Biovolume (reference stations)",
            "source_file": source_file,
            "trip_code": hit["TripCode"],
            "provenance": "AODN portal manual download (see docs/data_sources.md)",
        }
    )
    return out


def build_events(genus_path: Path, species_path: Path) -> pd.DataFrame:
    """All exceedance events from the genus file (4 genera) and species file (G. catenatum)."""
    genus = pd.read_csv(genus_path, low_memory=False)
    species = pd.read_csv(species_path, low_memory=False)
    parts = [
        exceedances(genus, name, EVENT_LEVELS[name], genus_path.name)
        for name in ("Karenia", "Alexandrium", "Pseudo-nitzschia", "Dinophysis")
    ]
    gc = "Gymnodinium catenatum"
    parts.append(exceedances(species, gc, EVENT_LEVELS[gc], species_path.name))
    events = pd.concat(parts, ignore_index=True)
    return events.sort_values(["date", "station_code", "taxon"]).reset_index(drop=True)[
        EVENT_COLUMNS
    ]


def main() -> None:
    """Write labels/events.csv and print a per-region/taxon summary."""
    events = build_events(latest("nrs_phyto_genus_*.csv"), latest("nrs_phyto_species_*.csv"))
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(EVENTS_PATH, index=False)
    print(f"wrote {len(events)} events -> {EVENTS_PATH}")
    summary = events.groupby(["region", "taxon"]).agg(
        events=("date", "size"),
        closure_level=("exceeds_closure_level", "sum"),
        first=("date", "min"),
        last=("date", "max"),
        max_cells_per_L=("cells_per_L", "max"),
    )
    print(summary.to_string())


if __name__ == "__main__":
    main()
