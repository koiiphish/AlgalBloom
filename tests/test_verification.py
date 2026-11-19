"""Phase 6 verification page: Biotoxin News parsing, outcomes, scores, status changes."""

import numpy as np
import pandas as pd
import pytest

from pipeline.forecast import score
from pipeline.labels import biotoxin_news as B
from pipeline.model.calibrate import Calibrator
from pipeline.publish import verification as V

# Lines as extracted by pypdf from the issue of 26 Oct 2026 (labels/raw/tas_biotoxin_news).
NEWS_TEXT = """SUMMARY OF RESULTS RECEIVED FOR WEEK COMMENCING MONDAY 19th OF
OCTOBER 2026
ISSUED: MONDAY 26th OF OCTOBER 2026
Biotoxin Results
Growing Area Sample Date Species PST (mg/Kg) AST (mg/Kg) DST (mg/Kg)
Flinders (SMP) 12/10/2026 Mussel <0.10
Moulting Bay 12/10/2026 Pacific Oyster <0.10 0.05 <0.01
Missionary Bay 14/10/2026 Pacific Oyster 0.95 <0.05 0.01
Toxin Producing Phytoplankton Results
Growing Area Sample Date Species Density (Cells/L)
Great Swanport 19/10/2026 Pseudo-nitzschia delicatissima group 12,000
Great Swanport 19/10/2026 Prorocentrum sp. 5,000
Pipeclay Lagoon 19/10/2026 Alexandrium tamarense Complex 200
Great Bay 20/10/2026 Dinophysis acuminata 800
Potentially Harmful Phytoplankton Species to Marine Fauna
Growing Area Sample Date Species Density (Cells/L) Mechanism*
Great Oyster Bay 19/10/2026 Chaetoceros sp. (Hyalochaete) 9,000 Mechanical Gill Necrosis
"""


def test_parse_biotoxin_news_tables():
    """Toxin rows keep missing values; phyto rows get PALT levels; the fauna table is skipped."""
    toxins, phyto = B.parse_text(NEWS_TEXT)
    assert len(toxins) == 3 and len(phyto) == 4
    flinders = toxins.iloc[0]
    assert (
        flinders["shellfish"] == "Mussel"
        and flinders["PST"] == "<0.10"
        and pd.isna(flinders["AST"])
    )
    assert toxins.iloc[1][["PST", "AST", "DST"]].tolist() == ["<0.10", "0.05", "<0.01"]
    assert (
        phyto.loc[phyto.species.str.startswith("Prorocentrum"), "lab_alert_cells_per_L"]
        .isna()
        .all()
    )
    assert B.issue_date(NEWS_TEXT) == pd.Timestamp("2026-10-26")


def test_notable_results():
    """Counts at/above PALT alert levels and toxins above limits are reported; others are not."""
    found = B.notable(*B.parse_text(NEWS_TEXT))
    text = " | ".join(found["finding"])
    assert "Alexandrium tamarense Complex 200" in text and "Dinophysis acuminata 800" in text
    assert "PST 0.95" in text  # above the 0.8 mg/kg limit
    assert "Pseudo-nitzschia" not in text  # 12,000 < 100,000


@pytest.mark.parametrize("species,level", [
    ("Alexandrium tamarense Complex", 100), ("Alexandrium sp.", None),
    ("Gymnodinium catenatum", 200), ("Gymnodinium sp.", 100_000),
    ("Dinophysis caudata", 500), ("Dinophysis acuminata", 200), ("Dinophysis sp.", None),
    ("Pseudo-nitzschia seriata group", 50_000), ("Pseudo-nitzschia sp.", None),
    ("Karenia brevis", 500), ("Karenia sp.", 100_000), ("Kareniaceae", None),
    ("Prorocentrum sp.", None), ("Chaetoceros sp.", None),
])  # fmt: skip
def test_lab_alert_mapping(species, level):
    """PALT levels only for names the PALT prints; genus-only and unlisted names get None."""
    assert B.lab_alert(species)[0] == level


def _deployment() -> score.Deployment:
    """Flat baseline 0, calibrator irrelevant here, climatology 0.1."""
    base = pd.DataFrame([{"area_id": "a", "month": m, "baseline": 0.0} for m in range(1, 13)])
    return score.Deployment(
        model_version="t", calibrator=Calibrator(x=[-1, 1], y=[0, 1]), cutoffs={"moderate": 0.5, "high": 0.8},
        baseline=base, climatology=base.rename(columns={"baseline": "clim_rate"}).assign(clim_rate=0.1),
        min_valid_pixels=5,
    )  # fmt: skip


def test_outcome_uses_the_forward_week_and_threshold():
    """Issue day 1: days 2-8 have anomaly log10(2)=0.30 > threshold 0.2 -> y = 1; the last days
    of the record are pending (their week is not complete)."""
    days = pd.date_range("2026-03-01", "2026-03-20")
    chl = pd.DataFrame({"area_id": "a", "date": days, "chl": 2.0, "n_valid": 10, "n_pixels": 10})
    thr = pd.DataFrame({"area_id": ["a"], "month": [3], "threshold": [0.2]})
    out = V.observed_outcomes(chl, _deployment(), ["a"], thr, days[0], days[-1]).set_index("date")
    assert out.loc["2026-03-01", "y"] == 1.0
    assert not out.loc["2026-03-15", "complete"] and np.isnan(out.loc["2026-03-15", "y"])


def test_summary_scores():
    """Brier scores and tier rates on a hand-made example."""
    v = pd.DataFrame({"issue_date": ["2026-03-01"] * 4, "area_id": list("abcd"),
                      "p": [0.9, 0.1, 0.5, 0.2], "tier": ["High", "Low", "Moderate", "Low"],
                      "y": [1.0, 0.0, np.nan, 1.0], "p_clim": [0.5] * 4,
                      "complete": [True, True, True, False]})  # fmt: skip
    s = V.summarise(v)
    assert s["verified"] == 3 and s["unverifiable_cloud"] == 1 and s["pending"] == 1
    assert s["brier"] == pytest.approx((0.01 + 0.01 + 0.64) / 3)
    assert s["brier_climatology"] == pytest.approx(0.25)
    assert s["tiers"]["Low"]["n"] == 2 and s["tiers"]["Low"]["rate"] == pytest.approx(0.5)


def test_status_changes_and_prior_tier(tmp_path):
    """A change between snapshots is listed with the highest tier issued in the 7 days before."""
    snaps = pd.DataFrame({
        "date": ["2026-11-20", "2026-11-21", "2026-11-22"], "region": "tas",
        "area_id": ["tas:great_bay:a"] * 3, "status": ["OPEN", "OPEN", "CLOSED"],
        "reason": ["", "", "biotoxins"], "growing_area": "Great Bay", "harvest_area": "A",
    })  # fmt: skip
    path = tmp_path / "snaps.csv"
    snaps.to_csv(path, index=False)
    meta = pd.DataFrame({"area_id": ["tas:great_bay:a"], "match_key": ["tas:great_bay:a"],
                         "growing_area": ["Great Bay"]})  # fmt: skip
    issued = pd.DataFrame({"issue_date": ["2026-11-19", "2026-11-21"], "area_id": "tas:great_bay:a",
                           "tier": ["Moderate", "High"]})  # fmt: skip
    ch = V.status_changes(meta, issued, path)
    assert len(ch) == 1 and ch.iloc[0]["change"] == "Open → Closed"
    assert ch.iloc[0]["tier_before"] == "High"
