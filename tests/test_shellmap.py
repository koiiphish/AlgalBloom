"""Tests for the ShellMAP notice parser and the label archiver helpers.

The fixture text is a short excerpt modelled on Classification Notice 2026/067
(© State of Tasmania, NRE Tas ShellMAP; reproduced for non-commercial testing). It covers
the awkward cases seen in the real notice: wrapped growing-area names, a date wrapped onto
the next line, a page header in the middle of a block, and every header label.
"""

import csv

import pytest

from pipeline.labels import archive
from pipeline.labels.shellmap import make_area_id, parse_notice, slug
from pipeline.labels.tas_lookup import match_key

NOTICE_TEXT = """Page 1 of 3
Primary Produce Safety (Seafood) Regulations 2023 - Classification Notice No. 2026/067
1. When classification notice takes effect
This classification notice takes effect on 1948hrs 16 November 2026, revokes and replaces
all previous classification notices and remains in force until revoked.
 Moulting Bay Growing Area
Zone 4 Harvest Area (Moulting Bay) OPEN
Classification
Zone 4 Harvest Area (Lease number(s) 9, 65) is classified as an approved area for the taking of all
species of regulated fish.
Current harvest status
Zone 4 Harvest Area is OPEN for the taking of all regulated fish from 1050hrs 02/11/2026.
Robbins Passage Harvest Area (Montagu) CLOSED
Classification
Robbins Passage Harvest Area (Lease number(s) 1) is classified as an approved area for the taking
of all species of regulated fish.
Current harvest status
Robbins Passage Harvest Area is CLOSED for the taking of all regulated fish from 0000hrs
Page 2 of 3
Primary Produce Safety (Seafood) Regulations 2023 - Classification Notice No. 2026/067
01/07/2023.
Kemps Bay Harvest Area (Duck Bay) OPEN (CONDITIONAL)
Classification
Kemps Bay Harvest Area (Lease number(s) 248) is classified as an approved area for the taking of all
species of regulated fish.
Current harvest status
Kemps Bay Harvest Area is OPEN for the taking of all regulated fish from 1030hrs 05/03/2026 subject
to the condition that the fish must be transferred to an approved wet storage facility.
DIVISION 2:  RESTRICTED AREAS/CONDITIONALLY RESTRICTED AREAS
Little Norfolk Bay Harvest Area (Little Norfolk
Bay) RESTRICTED
Classification
Little Norfolk Bay Harvest Area (Lease number(s) 14) is classified as a restricted area OPEN for the
taking of all species of regulated fish.
Gardners Bay Harvest Area (Gardners Bay) CONDITIONALLY RESTRICTED
Classification
Gardners Bay Harvest Area (Lease number(s) 136) is classified as a conditionally restricted area for
the taking of all species of regulated fish.
Current harvest status
Gardners Bay Harvest Area is CLOSED for the taking of all regulated fish from 1550hrs 05/09/2026.
DIVISION 3:  APPROVED AREAS (WILD HARVEST) TEMPORARILY CLOSED FOR
Abalone Block 16B All species of abalone of the
genus Haliotis
Closed 27 May 2025 for
biotoxins
Abalone Block 20B All species of abalone of the
genus Haliotis
Closed 16 October 2026 for
biotoxins
DIVISION 5:  RESTRICTED/CONDITIONALLY RESTRICTED AREAS CLOSED FOR
Prohibited Zone 1 Harvest Area (Moulting Bay) PROHIBITED
Classification
Prohibited Zone 1 Harvest Area (wild harvest) is classified as a restricted area that is closed for the
taking of all species of regulated fish.
Barnes Bay Harvest Area (Barnes Bay) NURSERY/SOURCE
Classification
Barnes Bay Harvest Area (wild harvest) is classified as a restricted area (nursery/source area) for the
taking of all species of regulated fish.
"""


@pytest.fixture(scope="module")
def notice():
    return parse_notice(NOTICE_TEXT)


def by_id(notice, area_id):
    return next(a for a in notice.areas if a.area_id == area_id)


def test_notice_identity(notice) -> None:
    assert notice.notice_id == "2026/067"
    assert notice.effective == "2026-11-16T19:48:00+11:00"


def test_all_headers_parsed(notice) -> None:
    farm = [a for a in notice.areas if not a.area_id.startswith("tas:abalone")]
    assert len(farm) == notice.n_headers_seen == 7


def test_open_area_with_since_time(notice) -> None:
    a = by_id(notice, "tas:moulting_bay:zone_4")
    assert (a.status, a.status_since) == ("OPEN", "2026-11-02T10:50:00+11:00")
    assert a.classification == "approved area"
    assert a.reason == "not stated in notice"


def test_date_wrapped_across_page_break(notice) -> None:
    a = by_id(notice, "tas:montagu:robbins_passage")
    assert a.status == "CLOSED"
    assert a.status_since == "2023-07-01T00:00:00+10:00"  # winter: AEST, +10:00


def test_conditional_open(notice) -> None:
    a = by_id(notice, "tas:duck_bay:kemps_bay")
    assert a.status == "OPEN_CONDITIONAL"
    assert "depuration" in a.reason


def test_wrapped_growing_area_and_restricted_without_status_sentence(notice) -> None:
    a = by_id(notice, "tas:little_norfolk_bay:little_norfolk_bay")
    assert a.growing_area == "Little Norfolk Bay"
    assert (a.status, a.status_since, a.classification) == ("OPEN", "", "restricted area")


def test_conditionally_restricted_closed(notice) -> None:
    a = by_id(notice, "tas:gardners_bay:gardners_bay")
    assert a.status == "CLOSED"
    assert a.classification == "conditionally restricted area"


def test_prohibited_and_nursery(notice) -> None:
    assert by_id(notice, "tas:moulting_bay:prohibited_zone_1").status == "PROHIBITED"
    assert by_id(notice, "tas:barnes_bay:barnes_bay").status == "NURSERY_SOURCE"


def test_abalone_blocks_have_reason(notice) -> None:
    a = by_id(notice, "tas:abalone:16b")
    assert (a.status, a.status_since, a.reason) == ("CLOSED", "2025-05-27", "biotoxins")
    assert by_id(notice, "tas:abalone:20b").status_since == "2026-10-16"


def test_unseen_header_label_is_detected() -> None:
    text = NOTICE_TEXT + "Mystery Harvest Area (Somewhere) TEMPORARILY SUSPENDED\n"
    n = parse_notice(text)
    with pytest.raises(ValueError, match="unexpected format"):
        archive.validate_notice(n, min_areas=1)


def test_missing_notice_id_raises() -> None:
    with pytest.raises(ValueError):
        parse_notice("no identifying header here")


def test_ids_and_matching() -> None:
    assert slug("Garfish Bay/Dart Island") == "garfish_bay_dart_island"
    assert make_area_id("Great Bay", "Zone North") == "tas:great_bay:zone_north"
    # notice "Zone North" == theLIST "North"; notice "Recherch" == theLIST "Recherche"
    assert match_key("tas:great_bay:zone_north") == match_key("tas:great_bay:north")
    assert match_key("tas:recherch_bay:recherch_bay") == "tas:recherche_bay:recherche_bay"


def test_append_snapshot_is_append_only_and_idempotent(notice, tmp_path) -> None:
    path = tmp_path / "snap.csv"
    rows = archive.snapshot_rows(notice, "2026-11-17", "2026-11-17T10:00:00+00:00", "abc")
    assert archive.append_snapshot(path, rows) == len(rows)
    assert archive.append_snapshot(path, rows) == 0  # same day + same source: skipped
    later = archive.snapshot_rows(notice, "2026-11-18", "2026-11-18T10:00:00+00:00", "abc")
    assert archive.append_snapshot(path, later) == len(rows)  # next day: appended
    with path.open(newline="", encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    assert len(data) == 2 * len(rows)
    assert list(data[0]) == archive.SNAPSHOT_COLUMNS
    assert data[0]["date"] == "2026-11-17"  # earlier rows untouched


def test_rate_limit_guard(tmp_path) -> None:
    path = tmp_path / "last_fetch.csv"
    assert not archive.already_fetched_today(path, "tas_shellmap", "2026-11-18")
    archive.record_fetch(path, "tas_shellmap", "2026-11-18")
    archive.record_fetch(path, "tas_biotoxin_news", "2026-11-17")
    assert archive.already_fetched_today(path, "tas_shellmap", "2026-11-18")
    assert not archive.already_fetched_today(path, "tas_shellmap", "2026-11-19")
    assert not archive.already_fetched_today(path, "tas_biotoxin_news", "2026-11-18")
