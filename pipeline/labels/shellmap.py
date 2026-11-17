"""Fetch and parse the Tasmanian ShellMAP "Current Harvest Status" classification notice.

The notice is a single PDF at a fixed URL that always holds the *current* notice
(each new notice "revokes and replaces all previous classification notices").
Structure verified on notice 2026/067 (see docs/data_sources.md):

    Zone 4 Harvest Area (Moulting Bay) OPEN
    Classification
    Zone 4 Harvest Area (Lease number(s) 9, 65) is classified as an approved area ...
    Current harvest status
    Zone 4 Harvest Area is OPEN for the taking of all regulated fish from 1050hrs 02/11/2026.

Wild abalone blocks appear in a table instead, and are the only entries with a stated reason:

    Abalone Block 16B All species of abalone of the genus Haliotis Closed 27 May 2025 for biotoxins

The notice never says *why* a farmed area is closed (biotoxins, rainfall, ...), so
`reason` is "not stated in notice" for those rows. Do not treat every closure as a HAB.
"""

import hashlib
import io
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from pypdf import PdfReader

from pipeline.http import get

NOTICE_URL = "https://nre.tas.gov.au/SiteAssets/ShellMAP%20Current%20Harvest%20Status.pdf"
BIOTOXIN_NEWS_URL = "https://nre.tas.gov.au/SiteAssets/Tasmanian%20Biotoxin%20News.pdf"
HOBART = ZoneInfo("Australia/Hobart")
REASON_NOT_STATED = "not stated in notice"

# Header labels printed after "(Growing Area)" on an area's first line.
HEADER_LABELS = (
    "OPEN (CONDITIONAL)",
    "NURSERY/SOURCE",
    "CONDITIONALLY RESTRICTED",
    "RESTRICTED",
    "PROHIBITED",
    "CLOSED",
    "OPEN",
)


@dataclass
class AreaStatus:
    """One area's status as printed in a notice (one row of the snapshot table)."""

    harvest_area: str
    growing_area: str
    header_label: str
    status: str  # OPEN | CLOSED | PARTIALLY_CLOSED | OPEN_CONDITIONAL | PROHIBITED |
    #              NURSERY_SOURCE | UNKNOWN
    status_since: str  # ISO datetime with Hobart offset, or "" if not printed
    classification: str  # e.g. "approved area", "conditionally restricted area"
    reason: str
    area_id: str

    def as_dict(self) -> dict[str, str]:
        """Plain dict for CSV writing."""
        return asdict(self)


@dataclass
class Notice:
    """A parsed notice: identity plus all area rows."""

    notice_id: str
    effective: str  # ISO datetime with Hobart offset
    areas: list[AreaStatus]
    n_headers_seen: int  # loose count of area headers, used to detect parsing gaps


# --- small helpers ------------------------------------------------------------------------------


def slug(text: str) -> str:
    """Lower-case, alphanumeric-and-underscore version of a name (for stable IDs)."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def make_area_id(growing_area: str, harvest_area: str) -> str:
    """Stable, name-based area ID, e.g. 'tas:moulting_bay:zone_4'."""
    return f"tas:{slug(growing_area)}:{slug(harvest_area)}"


def sha256(data: bytes) -> str:
    """Hex SHA-256 of some bytes (provenance fingerprint of a source file)."""
    return hashlib.sha256(data).hexdigest()


def squash(text: str) -> str:
    """Collapse all runs of whitespace (including line breaks) to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def parse_hhmm_ddmmyyyy(hhmm: str, ddmmyyyy: str) -> str:
    """'1050', '02/11/2026' -> '2026-11-02T10:50:00+11:00' (Hobart local time)."""
    dt = datetime.strptime(f"{ddmmyyyy} {hhmm}", "%d/%m/%Y %H%M").replace(tzinfo=HOBART)
    return dt.isoformat()


def parse_long_date(text: str) -> str:
    """'27 May 2025' -> '2025-05-27' (date only; no time is printed)."""
    return datetime.strptime(text, "%d %B %Y").date().isoformat()


# --- PDF -> text ---------------------------------------------------------------------------------

_PAGE_HEADER = re.compile(r"^(Page \d+ of \d+|Primary Produce Safety \(Seafood\) Regulations.*)$")


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Extract the raw text of every page of a PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def strip_page_headers(text: str) -> str:
    """Drop the repeated 'Page x of y' and regulation-title lines that interrupt area blocks."""
    return "\n".join(line for line in text.splitlines() if not _PAGE_HEADER.match(line.strip()))


# --- text -> rows --------------------------------------------------------------------------------

# An area header: "<harvest> Harvest Area (<growing>) <LABEL>". The growing-area name can wrap
# onto the next line (e.g. "(Little Norfolk\nBay)"), so [^)]* is allowed to span newlines.
_LABELS_RE = "|".join(re.escape(label) for label in HEADER_LABELS)
_HEADER = re.compile(
    rf"^(?P<ha>[^\n]+?) Harvest Area \((?P<ga>[^)]+)\)\s+(?P<label>{_LABELS_RE})[ \t]*$",
    re.MULTILINE,
)
# Loose version used only to count headers, so a header the strict regex misses is detected.
# Same shape, but accepts ANY upper-case label at the end of the line, so a header with a
# label we have never seen (and would therefore silently skip) still gets counted.
_LOOSE_HEADER = re.compile(
    r"^[^\n]+? Harvest Area \([^)]+\)[ \t]+[A-Z][A-Z/ ()]*[ \t]*$", re.MULTILINE
)
_STATUS = re.compile(
    r"Harvest Area is (?P<status>OPEN|CLOSED|PARTIALLY CLOSED) for the taking of .*? from "
    r"(?P<hhmm>\d{4})hrs (?P<date>\d{2}/\d{2}/\d{4})(?P<rest>[^.]*)"
)
_CLASSIFIED = re.compile(r"is classified as an? (?P<cls>.+?area)(?P<open> OPEN| CLOSED)?\b")
_NOTICE_ID = re.compile(r"Classification Notice No\. (\d{4}/\d{3})")
_EFFECTIVE = re.compile(r"takes effect on (\d{4})hrs (\d{1,2} \w+ \d{4})")
_ABALONE = re.compile(
    r"Abalone Block (?P<block>\w+) All species of abalone of the genus Haliotis "
    # reason = the run of lower-case words after "for" (stops at the next capitalised word)
    r"Closed (?P<date>\d{1,2} \w+ \d{4}) for (?P<reason>[a-z]+(?: [a-z]+)*)"
)


def _status_from_block(label: str, block: str) -> tuple[str, str, str]:
    """Work out (status, status_since, reason) for one area's text block."""
    m = _STATUS.search(block)
    if m:
        status = "CLOSED" if m["status"] != "OPEN" else "OPEN"
        if m["status"] == "PARTIALLY CLOSED":
            status = "PARTIALLY_CLOSED"
        reason = REASON_NOT_STATED
        if "subject to the condition" in m["rest"]:
            status = "OPEN_CONDITIONAL"
            reason = "open subject to depuration condition"
        return status, parse_hhmm_ddmmyyyy(m["hhmm"], m["date"]), reason
    # Restricted areas may have no "Current harvest status" sentence; the classification
    # sentence then says e.g. "classified as a restricted area OPEN for the taking of ...".
    c = _CLASSIFIED.search(block)
    if c and c["open"]:
        return c["open"].strip(), "", REASON_NOT_STATED
    if label == "PROHIBITED":
        return "PROHIBITED", "", "prohibited area"
    if label == "NURSERY/SOURCE":
        return "NURSERY_SOURCE", "", "restricted nursery/source area"
    return "UNKNOWN", "", REASON_NOT_STATED


def parse_areas(text: str) -> list[AreaStatus]:
    """Parse every '<harvest> Harvest Area (<growing>) LABEL' block in the notice text."""
    headers = list(_HEADER.finditer(text))
    rows = []
    for i, h in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = squash(text[h.end() : end].split("DIVISION")[0])
        ha, ga = squash(h["ha"]), squash(h["ga"])
        status, since, reason = _status_from_block(h["label"], block)
        c = _CLASSIFIED.search(block)
        rows.append(
            AreaStatus(
                harvest_area=ha,
                growing_area=ga,
                header_label=h["label"],
                status=status,
                status_since=since,
                classification=c["cls"] if c else "",
                reason=reason,
                area_id=make_area_id(ga, ha),
            )
        )
    return rows


def parse_abalone_blocks(text: str) -> list[AreaStatus]:
    """Parse the wild abalone block closures table (the only entries with a stated reason)."""
    rows = []
    for m in _ABALONE.finditer(squash(text)):
        name = f"Abalone Block {m['block']}"
        rows.append(
            AreaStatus(
                harvest_area=name,
                growing_area="wild abalone fishery",
                header_label="CLOSED",
                status="CLOSED",
                status_since=parse_long_date(m["date"]),
                classification="approved area (wild harvest)",
                reason=m["reason"].strip(),
                area_id=f"tas:abalone:{slug(m['block'])}",
            )
        )
    return rows


def parse_notice(text: str) -> Notice:
    """Parse the raw notice text into a Notice. Raises ValueError if the ID is missing."""
    nid = _NOTICE_ID.search(text)  # the ID lives in the page headers, so read it first
    if not nid:
        raise ValueError("Could not find 'Classification Notice No.' - layout may have changed")
    text = strip_page_headers(text)
    eff = _EFFECTIVE.search(squash(text))
    effective = ""
    if eff:
        dt = datetime.strptime(f"{eff[2]} {eff[1]}", "%d %B %Y %H%M").replace(tzinfo=HOBART)
        effective = dt.isoformat()
    areas = parse_areas(text) + parse_abalone_blocks(text)
    return Notice(
        notice_id=nid[1],
        effective=effective,
        areas=areas,
        n_headers_seen=len(_LOOSE_HEADER.findall(text)),
    )


def fetch_pdf(url: str) -> bytes:
    """Download a PDF once. No query string: nre.tas.gov.au robots.txt disallows '/*?*'."""
    resp = get(url)
    if not resp.content.startswith(b"%PDF"):
        raise ValueError(f"{url} did not return a PDF (got {resp.headers.get('content-type')})")
    return resp.content
