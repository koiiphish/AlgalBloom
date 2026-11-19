"""Parse the weekly Tasmanian Biotoxin News (NRE Tas, ShellMAP) into tables (Phase 6, D016).

The archiver (pipeline.labels.archive) saves each new issue as a PDF under
labels/raw/tas_biotoxin_news/. Each issue reports, per growing area and sample date:
  - "Biotoxin Results": shellfish flesh toxins PST / AST / DST (mg/kg), with "<" = not detected,
    NT = not tested, AC = analysis continuing
  - "Toxin Producing Phytoplankton Results": cell counts (cells/L) by species or group
  - "Potentially Harmful Phytoplankton Species to Marine Fauna": not parsed (fish-farm
    relevance, not shellfish safety)
Layout checked on the issue of 26 Oct 2026 (text extracted with pypdf).

Phytoplankton counts are compared with the ShellMAP Phytoplankton Action Level Table (PALT;
pipeline.labels.action_levels) ONLY where the reported name is one the PALT lists (Timothy,
2026-11-19: follow what is printed, no assumptions). Each listed species or group is checked on
its own count; reports at genus level ("Alexandrium sp.", "Dinophysis sp.", "Pseudo-nitzschia
sp.") or of unlisted taxa (e.g. "Kareniaceae", "Prorocentrum sp.") are not compared. The PALT's
note that levels are cumulative within a toxin group is not applied: the reading of that rule
for summing species with different levels is not specified in our source notes.
Toxin maximum limits are those printed in each issue (PST 0.8, AST 20, DST 0.16 mg/kg).

Licence: Tasmanian Government website licence, non-commercial use with acknowledgement
("© State of Tasmania (NRE Tas, ShellMAP)"; docs/data_sources.md).
"""

import glob
import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from pipeline.config import REPO_ROOT

NEWS_DIR = REPO_ROOT / "labels" / "raw" / "tas_biotoxin_news"
MAX_LIMITS = {"PST": 0.8, "AST": 20.0, "DST": 0.16}  # mg/kg, as printed in each issue

# PALT lab-alert levels (cells/L), matched only to names the PALT prints (PALT_VERBATIM in
# pipeline.labels.action_levels; PALT v6.1, Appendix 3). Most specific first.
#   "Alexandrium catenella/minutum/tamarense/ostenfeldii"  100   (a "tamarense Complex" report
#                                                                 names A. tamarense)
#   "Gymnodinium catenatum"                                 200
#   "Dinophysis acuminata/acuta/fortii"                     200
#   "Dinophysis caudata"                                    500
#   "Prorocentrum lima"                                     500
#   "Pseudo-nitzschia seriata group"                     50,000
#   "Pseudo-nitzschia delicatissima group"              100,000
#   "Karenia brevis"                                        500
#   "Karenia/Karlodinium/Gymnodinium group"             100,000  (reports naming one of these
#                                                                 genera; not G. catenatum)
LAB_ALERT_PATTERNS: list[tuple[str, float, str]] = [
    (r"^alexandrium (catenella|minutum|tamarense|ostenfeldii)\b", 100, "PST"),
    (r"^gymnodinium catenatum\b", 200, "PST"),
    (r"^dinophysis (acuminata|acuta|fortii)\b", 200, "DST"),
    (r"^dinophysis caudata\b", 500, "DST"),
    (r"^prorocentrum lima\b", 500, "DST"),
    (r"^pseudo-nitzschia seriata group\b", 50_000, "AST"),
    (r"^pseudo-nitzschia delicatissima group\b", 100_000, "AST"),
    (r"^karenia brevis\b", 500, "NST"),
    (r"^(karenia|karlodinium|gymnodinium)\b", 100_000, "NST"),
]

DATE = r"(\d{2}/\d{2}/\d{4})"
ROW = re.compile(rf"^(?P<area>.+?) {DATE} (?P<rest>.+?)\s*$")
TOXIN_VALUE = re.compile(r"^(<?\d+(\.\d+)?|NT|AC)$")
SECTIONS = {
    "Biotoxin Results": "toxins",
    "Toxin Producing Phytoplankton Results": "phyto",
    "Potentially Harmful Phytoplankton Species to Marine Fauna": "fauna",
}


def lab_alert(species: str) -> tuple[float | None, str | None]:
    """PALT lab-alert level (cells/L) and toxin group for a reported species, or (None, None)."""
    s = species.strip().lower()
    for pattern, level, toxin in LAB_ALERT_PATTERNS:
        if re.search(pattern, s):
            return level, toxin
    return None, None


def toxin_number(value: str | None) -> float | None:
    """'0.11' -> 0.11; '<0.10' (not detected), 'NT', 'AC' or missing -> None."""
    if value is None or pd.isna(value) or value.startswith("<") or value in ("NT", "AC"):
        return None
    return float(value)


def issue_date(text: str) -> pd.Timestamp | None:
    """The 'ISSUED: MONDAY 26th OF OCTOBER 2026' date, if present."""
    m = re.search(r"ISSUED:\s*\w+\s+(\d{1,2})(?:st|nd|rd|th)?\s+OF\s+(\w+)\s+(\d{4})", text)
    return (
        pd.to_datetime(f"{m.group(1)} {m.group(2)} {m.group(3)}", format="%d %B %Y") if m else None
    )


def parse_text(text: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(toxins, phyto) tables from the extracted text of one issue."""
    section, toxins, phyto = None, [], []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        for header, name in SECTIONS.items():
            if line.startswith(header):
                section = name
        m = ROW.match(line)
        if not m or section not in ("toxins", "phyto") or line.startswith("Growing Area"):
            continue
        area = m.group("area")
        date = pd.to_datetime(m.group(2), format="%d/%m/%Y")
        words = m.group("rest").split(" ")
        if section == "toxins":
            values = []
            while words and TOXIN_VALUE.match(words[-1]):
                values.insert(0, words.pop())
            values += [None] * (3 - len(values))
            toxins.append(
                {
                    "growing_area": area,
                    "sample_date": date,
                    "shellfish": " ".join(words),
                    "PST": values[0],
                    "AST": values[1],
                    "DST": values[2],
                }
            )
        else:
            if not re.fullmatch(r"[\d,]+", words[-1]):
                continue
            cells = float(words[-1].replace(",", ""))
            species = " ".join(words[:-1])
            level, toxin = lab_alert(species)
            phyto.append(
                {
                    "growing_area": area,
                    "sample_date": date,
                    "species": species,
                    "cells_per_L": cells,
                    "lab_alert_cells_per_L": level,
                    "toxin": toxin,
                }
            )
    return pd.DataFrame(toxins), pd.DataFrame(phyto)


def parse_pdf(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse one saved issue; adds the issue date and source file to every row."""
    text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    toxins, phyto = parse_text(text)
    issued = issue_date(text)
    for df in (toxins, phyto):
        if len(df):
            df["issued"] = issued
            df["source_file"] = path.name
    return toxins, phyto


def load_all(news_dir: Path = NEWS_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """All archived issues, de-duplicated (a sample can appear in more than one issue)."""
    parts = [parse_pdf(Path(f)) for f in sorted(glob.glob(str(news_dir / "*.pdf")))]
    toxins = (
        pd.concat([t for t, _ in parts if len(t)], ignore_index=True) if parts else pd.DataFrame()
    )
    phyto = (
        pd.concat([p for _, p in parts if len(p)], ignore_index=True) if parts else pd.DataFrame()
    )
    if len(toxins):
        toxins = toxins.drop_duplicates(["growing_area", "sample_date", "shellfish"], keep="last")
    if len(phyto):
        phyto = phyto.drop_duplicates(["growing_area", "sample_date", "species"], keep="last")
    return toxins, phyto


def notable(toxins: pd.DataFrame, phyto: pd.DataFrame) -> pd.DataFrame:
    """One row per growing area and sample date with any count at or above its PALT lab-alert
    level, or any toxin above its maximum limit. Columns: growing_area, sample_date, finding."""
    rows = []
    if len(phyto):
        hit = phyto[
            phyto["lab_alert_cells_per_L"].notna()
            & (phyto["cells_per_L"] >= phyto["lab_alert_cells_per_L"])
        ]
        for r in hit.itertuples():
            rows.append(
                (
                    r.growing_area,
                    r.sample_date,
                    f"{r.species} {r.cells_per_L:,.0f} cells/L "
                    f"(alert {r.lab_alert_cells_per_L:,.0f})",
                )
            )
    if len(toxins):
        for r in toxins.itertuples():
            for group, limit in MAX_LIMITS.items():
                v = toxin_number(getattr(r, group))
                if v is not None and v > limit:
                    rows.append(
                        (r.growing_area, r.sample_date, f"{group} {v} mg/kg (limit {limit})")
                    )
    return pd.DataFrame(rows, columns=["growing_area", "sample_date", "finding"])
