from __future__ import annotations

import shutil
from datetime import UTC, date, datetime

import httpx

from ..artifact_storage import validate_retained
from ..contracts import get_contract
from ..openstatesacquire import (
    AcquisitionDecision,
    RemoteDump,
    SavedDump,
    SnapshotNotPublished,
    decide_acquisition,
    dump_urls,
    previous_period,
)
from ..openstatesrefresh import require_openstates_snapshot_download_approval
from ..repositories.legislation import get_artifact
from .bulk import ArtifactSpec, data_root, download


def _probe(url: str, kind: str) -> RemoteDump:
    """Read the dump headers. A missing size stays missing so the caller can refuse it."""
    with httpx.Client(timeout=60.0, follow_redirects=True, headers={"User-Agent": "opendiscourse-research/0.1"}) as http:
        response = http.head(url)
    length_text = response.headers.get("content-length")
    length = int(length_text) if length_text and length_text.isdigit() else None
    return RemoteDump(
        kind=kind,
        url=url,
        status_code=response.status_code,
        content_length=length,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )


def _saved(artifact_key: str) -> SavedDump | None:
    row = get_artifact("openstates.dump", artifact_key)
    if row is None:
        return None
    metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
    return SavedDump(
        artifact_key=artifact_key,
        checksum=row["checksum_sha256"],
        status=row["status"],
        local_path=row["local_path"],
        metadata=metadata,
    )


def _reuse_or_download(decision: AcquisitionDecision, period: date) -> str:
    saved = _saved(decision.artifact_key) if decision.action == "reuse" else None
    if saved is not None:
        try:
            validate_retained(saved.local_path, saved.checksum or "")
        except (OSError, ValueError):
            saved = None
        else:
            return saved.local_path
    spec = ArtifactSpec(
        dataset_id="openstates.dump",
        artifact_key=decision.artifact_key,
        url=decision.url,
        filename=decision.filename,
        period_start=period,
        metadata=decision.metadata,
    )
    # overwrite stops an older saved month from hiding a file the publisher replaced.
    return str(download(spec, overwrite=decision.action == "download"))


def download_monthly_dump(
    year: int,
    month: int,
    *,
    include_schema: bool = True,
    include_data: bool = False,
    refresh: bool = False,
) -> list[str]:
    """Fetch the official OpenStates public pg_dump artifacts without restoring them.

    ``refresh`` checks the publisher headers first. The same ETag, modification
    time, and size reuse the saved file. A difference downloads a new copy and
    leaves the previous bytes in place. Without ``refresh``, a saved usable
    file is returned and the publisher is not asked again.
    """
    if include_data:
        require_openstates_snapshot_download_approval(get_contract("openstatesvotes"))
    period = date(year, month, 1)
    if not refresh:
        return _download_without_refresh(period, include_schema=include_schema, include_data=include_data)

    urls = dump_urls(year, month)
    remotes = {}
    if include_schema:
        remotes["schema"] = _probe(urls["schema"], "schema")
    if include_data:
        remotes["data"] = _probe(urls["data"], "data")
    # The decision asks for both kinds. A caller that wants only one kind still
    # probes the other so a partial month cannot be mistaken for a full snapshot,
    # then downloads only the requested kinds.
    if "schema" not in remotes:
        remotes["schema"] = _probe(urls["schema"], "schema")
    if "data" not in remotes:
        remotes["data"] = _probe(urls["data"], "data")
    saved = {
        f"schema-{period.strftime('%Y-%m')}": _saved(f"schema-{period.strftime('%Y-%m')}"),
        f"data-{period.strftime('%Y-%m')}": _saved(f"data-{period.strftime('%Y-%m')}"),
    }
    decisions = decide_acquisition(
        year,
        month,
        {kind: remote for kind, remote in remotes.items()},
        {key: row for key, row in saved.items() if row is not None},
        free_bytes=shutil.disk_usage(data_root()).free,
    )
    wanted = set()
    if include_schema:
        wanted.add("schema")
    if include_data:
        wanted.add("data")
    return [
        _reuse_or_download(decision, period)
        for decision in decisions
        if decision.kind in wanted
    ]


def resolve_published_month(year: int | None, month: int | None, *, today: date | None = None) -> tuple[int, int]:
    """Use the requested month, or the newest month whose dump address exists.

    The publisher says the automatic link can be missing for the first days of
    a month. An explicit month is never replaced with an older one. A missing
    explicit month raises ``SnapshotNotPublished``.
    """
    if (year is None) != (month is None):
        raise ValueError("pass both a year and a month, or neither")
    if year is not None and month is not None:
        urls = dump_urls(year, month)
        remote = _probe(urls["data"], "data")
        if remote.status_code == 404:
            raise SnapshotNotPublished(dump_urls(year, month)["data"])
        if remote.status_code != 200:
            raise ValueError(f"{urls['data']} returned HTTP {remote.status_code}")
        return year, month
    current = today or datetime.now(UTC).date()
    first = (current.year, current.month)
    second = previous_period(*first)
    for candidate in (first, second):
        remote = _probe(dump_urls(*candidate)["data"], "data")
        if remote.status_code == 200 and remote.content_length:
            return candidate
    raise SnapshotNotPublished(dump_urls(*first)["data"])


def _download_without_refresh(period: date, *, include_schema: bool, include_data: bool) -> list[str]:
    stamp = period.strftime("%Y-%m")
    urls = dump_urls(period.year, period.month)
    specs: list[ArtifactSpec] = []
    if include_data:
        specs.append(
            ArtifactSpec(
                dataset_id="openstates.dump",
                artifact_key=f"data-{stamp}",
                url=urls["data"],
                filename=f"openstates/{stamp}-public.pgdump",
                period_start=period,
                metadata={"kind": "data", "format": "pg_dump", "provider": "OpenStates", "requested_period": stamp},
            )
        )
    if include_schema:
        specs.insert(
            0,
            ArtifactSpec(
                dataset_id="openstates.dump",
                artifact_key=f"schema-{stamp}",
                url=urls["schema"],
                filename=f"openstates/{stamp}-schema.pgdump",
                period_start=period,
                metadata={"kind": "schema", "format": "pg_dump", "provider": "OpenStates", "requested_period": stamp},
            ),
        )
    return [str(download(spec)) for spec in specs]
