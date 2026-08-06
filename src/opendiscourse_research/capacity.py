"""Conservative preflight checks for all bulk acquisition workflows."""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic, sleep

import httpx

from .config import settings
from .ingestion.base import client

MiB = 1024 * 1024
GiB = 1024 * MiB

# A bulk plan preview calls remote_size() once per artifact -- hundreds of
# times for a multi-table ACS plan. Discovered live: unpaced back-to-back
# HEAD requests to the same publisher (Census) produced a high rate of
# timeouts, each costing a 45s wait plus a retry, turning a preview that
# should take minutes into the better part of an hour. Same fix as FRED's
# providers/fred.py::PACE_SECONDS.
PACE_SECONDS = 0.5
_last_probe = 0.0


@dataclass(frozen=True)
class RemoteObject:
    url: str
    bytes: int | None
    source: str = "remote"


def _probe_size(url: str) -> RemoteObject:
    with client() as http:
        response = http.head(url)
        if response.is_success and response.headers.get("content-length"):
            return RemoteObject(url, int(response.headers["content-length"]), "head")
        # Stream and close immediately: never turn a size probe into a full
        # download when a publisher ignores the Range header.
        with http.stream("GET", url, headers={"Range": "bytes=0-0"}) as response:
            response.raise_for_status()
            match = re.search(r"/(\d+)$", response.headers.get("content-range", ""))
            if match:
                return RemoteObject(url, int(match.group(1)), "range")
            if response.headers.get("content-length"):
                return RemoteObject(url, int(response.headers["content-length"]), "get")
    return RemoteObject(url, None, "unknown")


def remote_size(url: str) -> RemoteObject:
    """Obtain a published byte size without downloading the object.

    A one-byte range request is a safe fallback for publishers that do not
    implement HEAD. An unavailable size remains unknown and deliberately
    prevents automatic approval -- including when the probe itself fails
    (timeout, connection reset): one retry after a short pause absorbs a
    transient blip, but a persistent failure must not abort a preview
    covering many other artifacts. A bulk plan with hundreds of artifacts
    makes a network hiccup on any single one a near-certainty, not an edge
    case.
    """
    global _last_probe
    for attempt in range(2):
        wait = PACE_SECONDS - (monotonic() - _last_probe)
        if wait > 0:
            sleep(wait)
        try:
            result = _probe_size(url)
        except httpx.HTTPError:
            _last_probe = monotonic()
            if attempt == 0:
                sleep(2)
            continue
        _last_probe = monotonic()
        return result
    return RemoteObject(url, None, "error")


def storage_preview(
    objects: Iterable[RemoteObject],
    *,
    raw_path: Path | None = None,
    stage_multiplier: float = 1.0,
    database_multiplier: float = 1.5,
    reserve_bytes: int = 100 * GiB,
) -> dict:
    """Calculate peak space demand on the raw/database filesystem.

    The conservative default reserves one raw copy, one temporary stage copy,
    and 1.5x the raw size for PostgreSQL indexes and normalized records. A
    source contract can set more precise multipliers after a measured pilot.
    """
    items = list(objects)
    unknown = [item.url for item in items if item.bytes is None]
    download_bytes = sum(item.bytes or 0 for item in items)
    stage_bytes = int(download_bytes * stage_multiplier)
    database_bytes = int(download_bytes * database_multiplier)
    required_bytes = download_bytes + stage_bytes + database_bytes + reserve_bytes
    target = (raw_path or Path(settings.data_root)).resolve()
    target.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(target)
    free_after = disk.free - required_bytes
    return {
        "path": str(target),
        "filesystem_free_bytes": disk.free,
        "filesystem_total_bytes": disk.total,
        "download_bytes": download_bytes,
        "stage_bytes": stage_bytes,
        "database_bytes": database_bytes,
        "reserve_bytes": reserve_bytes,
        "peak_required_bytes": required_bytes,
        "free_after_bytes": free_after,
        "unknown_urls": unknown,
        "approved": not unknown and free_after >= 0,
        "reason": "sizes unavailable"
        if unknown
        else ("enough capacity" if free_after >= 0 else "insufficient capacity"),
        "objects": [asdict(item) for item in items],
    }
