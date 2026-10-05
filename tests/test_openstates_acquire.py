"""Monthly OpenStates dump decisions: address, change detection, and disk refusal."""

from __future__ import annotations

import pytest

from opendiscourse_research.openstatesacquire import (
    AcquisitionDecision,
    RemoteDump,
    SavedDump,
    SnapshotCapacityError,
    SnapshotNotPublished,
    decide_acquisition,
    dump_urls,
    previous_period,
    require_restore_capacity,
)

PERIOD = "2026-10"
URLS = dump_urls(2026, 10)
FREE = 200 * 1024 * 1024 * 1024


def _remote(kind: str, *, status: int = 200, length: int | None = 100, etag: str = "abc", modified: str = "Thu, 01 Oct 2026 00:00:00 GMT") -> RemoteDump:
    return RemoteDump(kind, URLS[kind], status, length, etag, modified)


def _saved(kind: str, *, etag: str = "abc", length: int = 100, modified: str = "Thu, 01 Oct 2026 00:00:00 GMT") -> SavedDump:
    return SavedDump(
        f"{kind}-{PERIOD}",
        "a" * 64,
        "downloaded",
        f"/lake/{kind}.pgdump",
        {"etag": etag, "content_length": length, "last_modified": modified},
    )


def test_urls_follow_the_official_year_month_pattern() -> None:
    assert URLS["data"] == "https://data.openstates.org/postgres/monthly/2026-10-public.pgdump"
    assert URLS["schema"] == "https://data.openstates.org/postgres/schema/2026-10-schema.pgdump"
    assert previous_period(2026, 1) == (2025, 12)


def test_matching_headers_reuse_the_saved_file() -> None:
    decisions = decide_acquisition(
        2026,
        10,
        {"data": _remote("data", length=1000), "schema": _remote("schema", length=50)},
        {"data-2026-10": _saved("data", length=1000), "schema-2026-10": _saved("schema", length=50)},
        free_bytes=1,
    )
    assert {item.action for item in decisions} == {"reuse"}


def test_a_changed_etag_downloads_without_deleting_the_old_copy() -> None:
    decisions = decide_acquisition(
        2026,
        10,
        {"data": _remote("data", length=1000, etag="new"), "schema": _remote("schema", length=50)},
        {"data-2026-10": _saved("data", length=1000), "schema-2026-10": _saved("schema", length=50)},
        free_bytes=FREE,
    )
    data = next(item for item in decisions if item.kind == "data")
    schema = next(item for item in decisions if item.kind == "schema")
    assert data.action == "download"
    assert schema.action == "reuse"
    assert data.metadata["etag"] == "new"
    assert "delete" not in data.reason


def test_missing_etag_does_not_pretend_the_saved_file_is_current() -> None:
    decisions = decide_acquisition(
        2026,
        10,
        {
            "data": _remote("data", length=1000, etag=""),
            "schema": _remote("schema", length=50),
        },
        {"data-2026-10": _saved("data", length=1000, etag=""), "schema-2026-10": _saved("schema", length=50)},
        free_bytes=FREE,
    )
    assert next(item.action for item in decisions if item.kind == "data") == "download"


def test_unknown_size_refuses_the_download() -> None:
    with pytest.raises(SnapshotCapacityError, match="size"):
        decide_acquisition(
            2026,
            10,
            {"data": _remote("data", length=None), "schema": _remote("schema", length=50)},
            {},
            free_bytes=FREE,
        )


def test_tight_disk_refuses_before_a_new_download() -> None:
    with pytest.raises(SnapshotCapacityError, match="refusing"):
        decide_acquisition(
            2026,
            10,
            {"data": _remote("data", length=10_000_000_000), "schema": _remote("schema", length=50)},
            {},
            free_bytes=30_000_000_000,
        )


def test_a_missing_month_is_not_replaced_inside_the_decision() -> None:
    with pytest.raises(SnapshotNotPublished):
        decide_acquisition(
            2026,
            10,
            {"data": _remote("data", status=404, length=None), "schema": _remote("schema")},
            {},
            free_bytes=FREE,
        )


def test_capacity_math_keeps_room_for_the_candidate_database() -> None:
    report = require_restore_capacity(data_bytes=10, schema_bytes=2, free_bytes=10**18)
    assert report["candidate_bytes"] == 40
    assert report["required_bytes"] == 12 + 40 + report["reserve_bytes"]


def test_decision_uses_only_the_official_address() -> None:
    remote = RemoteDump("data", "https://example.test/2026-10-public.pgdump", 200, 10, "abc", "now")
    with pytest.raises(ValueError, match="missing official"):
        decide_acquisition(2026, 10, {"data": remote, "schema": _remote("schema")}, {}, free_bytes=FREE)
    assert isinstance(
        decide_acquisition(
            2026,
            10,
            {"data": _remote("data"), "schema": _remote("schema")},
            {},
            free_bytes=FREE,
        )[0],
        AcquisitionDecision,
    )
