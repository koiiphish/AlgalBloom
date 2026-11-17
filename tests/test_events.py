"""Tests for the harmful-taxon events table (pipeline.labels.events)."""

import pandas as pd

from pipeline.labels.action_levels import EVENT_LEVELS, PALT_VERBATIM
from pipeline.labels.events import EVENT_COLUMNS, exceedances


def _wide_table() -> pd.DataFrame:
    """A tiny NRS-style wide table: one row per sample, one column per taxon."""
    return pd.DataFrame(
        {
            "StationCode": ["GSV", "GSV", "MAI", "VBM"],
            "StationName": ["Gulf St Vincent", "Gulf St Vincent", "Maria Island", "Bonney"],
            "Latitude": [-35.0, -35.0, -42.6, -38.4],
            "Longitude": [138.5, 138.5, 148.2, 141.3],
            "TripCode": ["A", "B", "C", "D"],
            "SampleTime_Local": [
                "2025-07-03 11:22:00",
                "2025-05-01 09:10:00",
                "2023-01-12 10:00:00",
                "2025-01-01 09:00:00",
            ],
            "SampleDepth_m": ["WC", "WC", "WC", "WC"],
            "Karenia": [113_000, 50, 510, 100_000],
        }
    )


def test_threshold_region_and_closure_flag() -> None:
    out = exceedances(_wide_table(), "Karenia", EVENT_LEVELS["Karenia"], "f.csv")
    # 50 cells/L is below the 500 lab-alert level; VBM (Victoria) is excluded.
    assert out["trip_code"].tolist() == ["A", "C"]
    assert out["region"].tolist() == ["sa", "tas"]
    assert out["exceeds_closure_level"].tolist() == [True, False]  # closure level 5000
    assert out["karenia_group_level_exceeded"].tolist() == [True, False]  # 100,000
    assert out["date"].tolist() == ["2025-07-03", "2023-01-12"]
    assert list(out.columns) == EVENT_COLUMNS


def test_event_levels_match_palt() -> None:
    """Applied levels must come from the published table, not be invented."""
    assert EVENT_LEVELS["Karenia"].lab_alert == PALT_VERBATIM["Karenia brevis"][0]
    assert (
        EVENT_LEVELS["Alexandrium"].closure
        == PALT_VERBATIM["Alexandrium catenella/minutum/tamarense/ostenfeldii"][2]
    )
    assert EVENT_LEVELS["Pseudo-nitzschia"].lab_alert == min(
        PALT_VERBATIM["Pseudo-nitzschia seriata group"][0],
        PALT_VERBATIM["Pseudo-nitzschia delicatissima group"][0],
    )
    assert EVENT_LEVELS["Dinophysis"].closure is None
