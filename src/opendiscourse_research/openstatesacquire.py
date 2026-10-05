"""Decide how an OpenStates monthly dump is found and whether it must be fetched again.

The publisher documents one address pattern and says the current month's file
keeps changing. The month and year only find the address. The file's own
size, ETag, and last-modified time say whether the bytes we already saved are
still the bytes at that address. The SHA-256 recorded after download is the
identity. This module does not download or restore anything.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

GiB = 1024 * 1024 * 1024
# July's 10.7 GB dump restored to about 38 GB. Four times the compressed size
# covers that candidate database. The download itself is an extra copy.
CANDIDATE_DATABASE_MULTIPLIER = 4
RESTORE_RESERVE_BYTES = 20 * GiB
DATA_URL = "https://data.openstates.org/postgres/monthly/{period}-public.pgdump"
SCHEMA_URL = "https://data.openstates.org/postgres/schema/{period}-schema.pgdump"


class SnapshotNotPublished(FileNotFoundError):
    """The requested month has no public dump yet."""


class SnapshotCapacityError(ValueError):
    """The publisher size is unknown, or the disk cannot hold the restore."""


@dataclass(frozen=True)
class RemoteDump:
    """Headers for one official dump address. No body is downloaded."""

    kind: str
    url: str
    status_code: int
    content_length: int | None
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True)
class SavedDump:
    """The newest saved copy of one month's artifact key."""

    artifact_key: str
    checksum: str | None
    status: str
    local_path: str
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class AcquisitionDecision:
    """Reuse a validated copy, or download because the remote file may differ."""

    kind: str
    artifact_key: str
    url: str
    filename: str
    action: str
    reason: str
    metadata: dict[str, object]


def period_stamp(year: int, month: int) -> str:
    """Return ``YYYY-MM`` after rejecting a month that is not a real month."""
    return date(year, month, 1).strftime("%Y-%m")


def dump_urls(year: int, month: int) -> dict[str, str]:
    """Return the official data and schema addresses for one month."""
    period = period_stamp(year, month)
    return {
        "data": DATA_URL.format(period=period),
        "schema": SCHEMA_URL.format(period=period),
    }


def previous_period(year: int, month: int) -> tuple[int, int]:
    """Return the calendar month before ``year`` and ``month``."""
    current = date(year, month, 1)
    earlier = date(current.year - 1, 12, 1) if current.month == 1 else date(current.year, current.month - 1, 1)
    return earlier.year, earlier.month


def _header_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().strip('"')
    return text or None


def remote_identity_metadata(remote: RemoteDump, period: str) -> dict[str, object]:
    """Record the headers that a later month must compare."""
    return {
        "kind": remote.kind,
        "format": "pg_dump",
        "provider": "OpenStates",
        "requested_period": period,
        "content_length": remote.content_length,
        "etag": _header_text(remote.etag),
        "last_modified": _header_text(remote.last_modified),
        "official_url": remote.url,
    }


def _same_remote(saved: SavedDump | None, remote: RemoteDump) -> bool:
    if saved is None or not saved.checksum or saved.local_path.startswith("virtual://"):
        return False
    if saved.status in {"failed", "downloading", "planned"}:
        return False
    etag = _header_text(remote.etag)
    modified = _header_text(remote.last_modified)
    if not etag or not modified or remote.content_length is None:
        return False
    metadata = saved.metadata or {}
    saved_etag = metadata.get("etag")
    saved_modified = metadata.get("last_modified")
    return (
        isinstance(saved_etag, str)
        and isinstance(saved_modified, str)
        and _header_text(saved_etag) == etag
        and _header_text(saved_modified) == modified
        and metadata.get("content_length") == remote.content_length
    )


def require_restore_capacity(*, data_bytes: int, schema_bytes: int, free_bytes: int) -> dict[str, int]:
    """Refuse an unknown size or a disk that cannot hold the download and a candidate database."""
    if data_bytes <= 0 or schema_bytes <= 0:
        raise SnapshotCapacityError("refusing the download because the publisher size is unknown")
    download_bytes = data_bytes + schema_bytes
    candidate_bytes = data_bytes * CANDIDATE_DATABASE_MULTIPLIER
    required = download_bytes + candidate_bytes + RESTORE_RESERVE_BYTES
    if free_bytes < required:
        raise SnapshotCapacityError(
            f"refusing the download: need {required} bytes free and have {free_bytes}"
        )
    return {
        "download_bytes": download_bytes,
        "candidate_bytes": candidate_bytes,
        "reserve_bytes": RESTORE_RESERVE_BYTES,
        "required_bytes": required,
        "free_bytes": free_bytes,
    }


def decide_acquisition(
    year: int,
    month: int,
    remotes: Mapping[str, RemoteDump],
    saved: Mapping[str, SavedDump],
    *,
    free_bytes: int,
) -> list[AcquisitionDecision]:
    """Choose reuse or download for the data dump and the schema dump.

    A requested month that is missing is an error. Callers that want the
    newest published month try the previous month themselves. A matching
    ETag, last-modified time, and size can reuse a saved file. Any missing
    or different header downloads again. The old file is kept by the artifact
    store; this decision never says to delete it.
    """
    period = period_stamp(year, month)
    urls = dump_urls(year, month)
    decisions: list[AcquisitionDecision] = []
    sizes: dict[str, int] = {}
    for kind in ("schema", "data"):
        remote = remotes.get(kind)
        expected = urls[kind]
        if remote is None or remote.url != expected or remote.kind != kind:
            raise ValueError(f"missing official {kind} probe for {period}")
        if remote.status_code == 404:
            raise SnapshotNotPublished(f"{period} {kind} dump is not published at {expected}")
        if remote.status_code != 200:
            raise ValueError(f"{expected} returned HTTP {remote.status_code}")
        if remote.content_length is None or remote.content_length <= 0:
            raise SnapshotCapacityError(f"refusing {expected}: publisher did not give a size")
        sizes[kind] = remote.content_length
        key = f"{kind}-{period}"
        filename = (
            f"openstates/{period}-public.pgdump"
            if kind == "data"
            else f"openstates/{period}-schema.pgdump"
        )
        metadata = remote_identity_metadata(remote, period)
        current = saved.get(key)
        if _same_remote(current, remote):
            action, reason = "reuse", "etag, last-modified, and size match the saved file"
        else:
            action, reason = "download", "remote file is new or its headers differ from the saved file"
        decisions.append(
            AcquisitionDecision(
                kind=kind,
                artifact_key=key,
                url=expected,
                filename=filename,
                action=action,
                reason=reason,
                metadata=metadata,
            )
        )
    if any(decision.action == "download" for decision in decisions):
        require_restore_capacity(
            data_bytes=sizes["data"], schema_bytes=sizes["schema"], free_bytes=free_bytes
        )
    return decisions


def assert_official_url(url: str) -> None:
    """Reject a dump address that is not the documented monthly pattern."""
    if re.fullmatch(r"https://data\.openstates\.org/postgres/(?:monthly|schema)/\d{4}-\d{2}-(?:public|schema)\.pgdump", url) is None:
        raise ValueError(f"refusing unofficial dump address {url}")
