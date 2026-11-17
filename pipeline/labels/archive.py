"""Daily label archiver: snapshot official harvest-area statuses into an append-only CSV.

Run:  uv run python -m pipeline.labels.archive

Requests per run: one GET of the ShellMAP status PDF and one GET of Tasmanian Biotoxin
News (brief: at most one request per page per day). SA (SASQAP) is skipped until PIRSA
confirms automated access is acceptable (see docs/data_sources.md).

Exit codes (the GitHub workflow commits whatever was written, then fails on non-zero):
  0 = all good
  1 = hard failure: the status notice could not be fetched/parsed; nothing appended
  2 = data written, but something needs a human look (unknown area names, Biotoxin News
      failed, ...). The messages printed explain what.
"""

import csv
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pipeline.config import REPO_ROOT
from pipeline.labels import sa_sasqap
from pipeline.labels.shellmap import (
    BIOTOXIN_NEWS_URL,
    HOBART,
    NOTICE_URL,
    Notice,
    fetch_pdf,
    parse_notice,
    pdf_to_text,
    sha256,
)
from pipeline.labels.tas_lookup import KNOWN_WITHOUT_POLYGON, load_lookup, match_key

LABELS_DIR = REPO_ROOT / "labels"
SNAPSHOT_PATH = LABELS_DIR / "status_snapshots.csv"
RAW_DIR = LABELS_DIR / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.csv"

SNAPSHOT_COLUMNS = [
    # columns specified in the brief
    "date", "region", "area_id", "status", "reason", "source_url", "retrieved_at",
    # extra columns agreed in the Phase 1 plan
    "notice_id", "status_since", "classification", "harvest_area", "growing_area",
    "source_sha256",
]  # fmt: skip
MANIFEST_COLUMNS = ["retrieved_at", "source", "url", "path", "bytes", "sha256"]
# Records the Hobart date each source was last requested, so we never request a page more
# than once per (Hobart) day, even if the workflow is re-run manually.
LAST_FETCH_PATH = RAW_DIR / "last_fetch.csv"
MIN_TAS_AREAS = 45  # notice 2026/067 has 57 farm/wild areas; far fewer means a parsing problem


@dataclass
class RunReport:
    """Collects problems that should make the run 'fail loudly' after writing data."""

    problems: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        """Record and print a problem."""
        print(f"PROBLEM: {message}", flush=True)
        self.problems.append(message)


# --- pure helpers (unit-tested) -----------------------------------------------------------------


def validate_notice(notice: Notice, min_areas: int = MIN_TAS_AREAS) -> None:
    """Raise ValueError if the parsed notice looks incomplete."""
    farm = [a for a in notice.areas if not a.area_id.startswith("tas:abalone")]
    if len(farm) != notice.n_headers_seen:
        raise ValueError(
            f"Parsed {len(farm)} area blocks but saw {notice.n_headers_seen} headers: "
            "a header has an unexpected format (new status label?)."
        )
    if len(farm) < min_areas:
        raise ValueError(f"Only {len(farm)} areas parsed (expected >= {min_areas}).")
    unknown = [a.area_id for a in notice.areas if a.status == "UNKNOWN"]
    if unknown:
        raise ValueError(f"Could not determine status for: {unknown}")


def snapshot_rows(
    notice: Notice, date: str, retrieved_at: str, source_sha: str
) -> list[dict[str, str]]:
    """Turn a parsed notice into snapshot CSV rows (one per area)."""
    return [
        {
            "date": date,
            "region": "tas",
            "area_id": a.area_id,
            "status": a.status,
            "reason": a.reason,
            "source_url": NOTICE_URL,
            "retrieved_at": retrieved_at,
            "notice_id": notice.notice_id,
            "status_since": a.status_since,
            "classification": a.classification,
            "harvest_area": a.harvest_area,
            "growing_area": a.growing_area,
            "source_sha256": source_sha,
        }
        for a in notice.areas
    ]


def append_snapshot(path: Path, rows: list[dict[str, str]]) -> int:
    """Append rows to the snapshot CSV; never rewrite existing rows.

    Idempotent: if rows for the same (date, region, source_sha256) are already present
    (e.g. a manual re-run on the same day), nothing is appended. Returns rows written.
    """
    if not rows:
        return 0
    key = (rows[0]["date"], rows[0]["region"], rows[0]["source_sha256"])
    exists = path.exists()
    if exists:
        with path.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if (r["date"], r["region"], r["source_sha256"]) == key:
                    return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SNAPSHOT_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def unknown_area_ids(notice: Notice, lookup_keys: set[str]) -> list[str]:
    """Area IDs in the notice that match no theLIST polygon and are not known exceptions."""
    return sorted(
        a.area_id
        for a in notice.areas
        if not a.area_id.startswith("tas:abalone")
        and a.area_id not in KNOWN_WITHOUT_POLYGON
        and match_key(a.area_id) not in lookup_keys
    )


def save_raw(data: bytes, path: Path, source: str, url: str, retrieved_at: str) -> bool:
    """Save a raw source file (if not already saved) and log it in the manifest."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    new_manifest = not MANIFEST_PATH.exists()
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        if new_manifest:
            writer.writeheader()
        writer.writerow(
            {
                "retrieved_at": retrieved_at,
                "source": source,
                "url": url,
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "bytes": len(data),
                "sha256": sha256(data),
            }
        )
    return True


def read_last_fetch(path: Path) -> dict[str, str]:
    """{source: hobart_date} of the last request made to each source."""
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {r["source"]: r["hobart_date"] for r in csv.DictReader(f)}


def record_fetch(path: Path, source: str, hobart_date: str) -> None:
    """Remember that `source` was requested on `hobart_date` (one row per source)."""
    state = read_last_fetch(path)
    state[source] = hobart_date
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "hobart_date"])
        writer.writerows(sorted(state.items()))


def already_fetched_today(path: Path, source: str, hobart_date: str) -> bool:
    """True if `source` was already requested on this Hobart date (rate-limit guard)."""
    return read_last_fetch(path).get(source) == hobart_date


# --- the run --------------------------------------------------------------------------------------


def archive_tas_status(report: RunReport, now: datetime) -> None:
    """Fetch, parse, validate and append today's Tasmanian status snapshot."""
    retrieved_at = now.isoformat(timespec="seconds")
    date = now.astimezone(HOBART).date().isoformat()
    if already_fetched_today(LAST_FETCH_PATH, "tas_shellmap", date):
        print(f"tas: already requested on {date} (Hobart); skipping to respect 1 request/day")
        return
    record_fetch(LAST_FETCH_PATH, "tas_shellmap", date)  # record before fetching: a failed
    pdf = fetch_pdf(NOTICE_URL)  # request still counts as a request
    digest = sha256(pdf)
    notice = parse_notice(pdf_to_text(pdf))
    validate_notice(notice)  # raises -> hard failure, nothing appended

    raw_name = f"{notice.notice_id.replace('/', '-')}_{digest[:8]}.pdf"
    if save_raw(pdf, RAW_DIR / "tas_shellmap" / raw_name, "tas_shellmap", NOTICE_URL, retrieved_at):
        print(f"saved new notice PDF {raw_name}")

    written = append_snapshot(SNAPSHOT_PATH, snapshot_rows(notice, date, retrieved_at, digest))
    print(f"tas: notice {notice.notice_id}, {len(notice.areas)} areas, {written} rows appended")

    unknown = unknown_area_ids(notice, set(load_lookup()))
    if unknown:
        report.warn(f"Area names not in theLIST lookup (new or renamed areas?): {unknown}")


def archive_biotoxin_news(report: RunReport, now: datetime) -> None:
    """Save the weekly Biotoxin News PDF whenever its content changes (raw only, for now)."""
    retrieved_at = now.isoformat(timespec="seconds")
    hobart_date = now.astimezone(HOBART).date().isoformat()
    if already_fetched_today(LAST_FETCH_PATH, "tas_biotoxin_news", hobart_date):
        print(f"biotoxin news: already requested on {hobart_date} (Hobart); skipping")
        return
    record_fetch(LAST_FETCH_PATH, "tas_biotoxin_news", hobart_date)
    try:
        pdf = fetch_pdf(BIOTOXIN_NEWS_URL)
    except Exception as err:  # noqa: BLE001 - any failure here should not block the notice
        report.warn(f"Biotoxin News fetch failed: {err}")
        return
    digest = sha256(pdf)
    already = MANIFEST_PATH.exists() and digest in MANIFEST_PATH.read_text(encoding="utf-8")
    if already:
        print("biotoxin news: unchanged")
        return
    name = f"{now.astimezone(HOBART):%Y-%m-%d}_{digest[:8]}.pdf"
    save_raw(pdf, RAW_DIR / "tas_biotoxin_news" / name, "tas_biotoxin_news", BIOTOXIN_NEWS_URL,
             retrieved_at)  # fmt: skip
    print(f"biotoxin news: saved new edition {name}")


def main() -> int:
    """Run all label sources; return the process exit code (see module docstring)."""
    now = datetime.now(UTC)
    report = RunReport()
    try:
        archive_tas_status(report, now)
    except Exception as err:  # noqa: BLE001 - report clearly, then fail hard
        print(f"HARD FAILURE (tas status): {type(err).__name__}: {err}", flush=True)
        archive_biotoxin_news(report, now)  # still try to keep the weekly newsletter
        return 1
    archive_biotoxin_news(report, now)
    print(sa_sasqap.status_message())
    return 2 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
