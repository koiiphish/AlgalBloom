"""Phytoplankton action levels (cells/L) used to define a 'harmful-taxon event'.

Source: ShellMAP Biotoxin Management Plan, Version 6.1, NRE Tasmania (PDF dated 2025-12-24),
Appendix 3 "Phytoplankton (Algal) Action Level Table (PALT)", page 29,
https://nre.tas.gov.au/Documents/ShellMAP%20Biotoxin%20Management%20Plan.pdf
(read 2026-11-17; the table was checked visually from a rendered page image).

Columns in the PALT:
  lab_alert      = "Alert Level for AST to contact ShellMAP immediately"
  grower_alert   = "Alert Level for ShellMAP to contact growers"
  closure        = "Alert Level to initiate closure pending flesh testing results"
Levels are cumulative within a toxin group (PALT note).

Our station data is mostly at GENUS level, while the PALT is mostly per species/group.
Genus mapping (decision D009) uses the most precautionary (lowest) level of any listed
species in the genus, as the PALT itself applies species PALs to "sp./spp." reports.
These are Tasmanian levels; we apply them to SA stations too, as one consistent yardstick.
"""

from dataclasses import dataclass

PALT_SOURCE = "ShellMAP Biotoxin Management Plan v6.1 (NRE Tas, 2025), Appendix 3 PALT, p.29"


@dataclass(frozen=True)
class ActionLevel:
    """Action levels for one taxon as used in events.csv (cells per litre)."""

    taxon: str
    toxin: str
    lab_alert: float
    closure: float | None  # None where the PALT gives no closure-pending-testing level
    basis: str  # how the level was derived from the PALT (for provenance)


# Exactly as printed in the PALT (verbatim values; for reference and tests).
PALT_VERBATIM = {
    "Alexandrium catenella/minutum/tamarense/ostenfeldii": (100, 200, 500),
    "Gymnodinium catenatum": (200, "1000 mussels / 2000 other", 5000),
    "Dinophysis acuminata/acuta/fortii": (200, 1000, None),
    "Dinophysis caudata": (500, 1000, None),
    "Prorocentrum lima": (500, 500, None),
    "Pseudo-nitzschia seriata group": (50_000, 50_000, 500_000),
    # The closure cell is printed between the two Pseudo-nitzschia rows (ambiguous layout).
    "Pseudo-nitzschia delicatissima group": (100_000, 500_000, "500,000 (ambiguous row)"),
    "Karenia brevis": (500, 1000, 5000),
    "Karenia/Karlodinium/Gymnodinium group": (100_000, 250_000, 300_000),
}

# Levels applied to our (mostly genus-level) counts.
EVENT_LEVELS = {
    "Alexandrium": ActionLevel(
        "Alexandrium", "PST", 100, 500, "genus; all four listed species share 100/200/500"
    ),
    "Gymnodinium catenatum": ActionLevel(
        "Gymnodinium catenatum", "PST", 200, 5000, "species; PALT row as printed"
    ),
    "Dinophysis": ActionLevel(
        "Dinophysis", "DST", 200, None, "genus; lowest listed species level (200); no closure level"
    ),
    "Pseudo-nitzschia": ActionLevel(
        "Pseudo-nitzschia",
        "AST",
        50_000,
        500_000,
        "genus; size groups not separable in our data, so lowest group level (seriata)",
    ),
    "Karenia": ActionLevel(
        "Karenia",
        "NST",
        500,
        5000,
        "genus; K. brevis level (lowest). K./Karlodinium/Gymnodinium group would be "
        "100,000 / 300,000. Both are reported in events.csv",
    ),
}

# Secondary, less precautionary Karenia level (the K./Karlodinium/Gymnodinium group),
# reported alongside so the effect of the choice is visible.
KARENIA_GROUP_LEVEL = ActionLevel(
    "Karenia", "NST", 100_000, 300_000, "Karenia/Karlodinium/Gymnodinium group row"
)
