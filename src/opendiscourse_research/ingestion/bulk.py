from __future__ import annotations

import fcntl
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from mimetypes import guess_type
from pathlib import Path
from typing import Any

import yaml

from ..artifact_storage import file_checksum, retain_artifact_bytes, validate_retained
from ..config import settings
from ..repositories.legislation import get_artifact, register_artifact
from .base import client


@dataclass(frozen=True)
class ArtifactSpec:
    dataset_id: str
    artifact_key: str
    url: str
    filename: str
    period_start: date | None = None
    period_end: date | None = None
    metadata: dict | None = None


def data_root() -> Path:
    root = Path(settings.data_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def artifact_path(spec: ArtifactSpec) -> Path:
    path = data_root() / spec.dataset_id.replace(".", "/") / spec.filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _retained_path(spec: ArtifactSpec, checksum: str) -> Path:
    """Return the immutable lake destination for one verified byte sequence."""
    original = artifact_path(spec)
    return original.with_name(f"{original.stem}.{checksum}{original.suffix}")


def _retain(spec: ArtifactSpec, source: Path, checksum: str, *, move: bool) -> Path:
    """Put verified bytes at their checksum-specific path before catalog admission."""
    return retain_artifact_bytes(
        source, checksum, destination=_retained_path(spec, checksum), move=move
    )


def _upsert(spec: ArtifactSpec, path: Path, status: str, **values: object) -> None:
    register_artifact(
        spec.dataset_id,
        spec.url,
        str(path),
        spec.artifact_key,
        status=status,
        checksum_sha256=values.get("checksum")
        if isinstance(values.get("checksum"), str)
        else None,
        bytes_downloaded=values.get("bytes")
        if isinstance(values.get("bytes"), int)
        else None,
        period_start=str(spec.period_start) if spec.period_start else None,
        period_end=str(spec.period_end) if spec.period_end else None,
        content_type=values.get("content_type")
        if isinstance(values.get("content_type"), str)
        else None,
        error_message=values["error"]
        if isinstance(values.get("error"), str)
        else None,
        metadata=spec.metadata or {},
    )


def download(
    spec: ArtifactSpec, *, overwrite: bool = False, chunk_size: int = 1024 * 1024
) -> Path:
    """Atomically download an artifact and register its checksum/coverage state."""
    target = artifact_path(spec)
    # Keep the lock inode stable: unlinking it would allow two independent locks.
    with target.with_suffix(target.suffix + ".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _download_locked(spec, overwrite=overwrite, chunk_size=chunk_size)


def _download_locked(spec: ArtifactSpec, *, overwrite: bool, chunk_size: int) -> Path:
    """Resume a stable staging file while holding its interprocess lock."""
    target = artifact_path(spec)
    partial = target.with_suffix(target.suffix + ".part")
    latest = None
    if not overwrite:
        # A failed latest version is an unfinished refresh: fall through so this
        # call resumes it (Story 1.7 spec) rather than returning the older bytes.
        latest = get_artifact(spec.dataset_id, spec.artifact_key)
        if (
            latest
            and latest["checksum_sha256"]
            and not latest["local_path"].startswith("virtual://")
            and latest["status"] not in {"failed", "downloading", "planned"}
        ):
            try:
                validate_retained(latest["local_path"], latest["checksum_sha256"])
            except (ValueError, OSError):
                pass
            else:
                return Path(latest["local_path"])
    if (
        target.exists()
        and not overwrite
        and (
            latest is None
            or latest["status"] not in {"failed", "downloading", "planned"}
        )
    ):
        digest = file_checksum(target)
        retained = _retain(spec, target, digest, move=False)
        _upsert(
            spec, retained, "skipped", bytes=retained.stat().st_size, checksum=digest
        )
        return retained
    headers: dict[str, str] = {}
    mode = "wb"
    existing = partial.stat().st_size if partial.exists() else 0
    if existing:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"
    try:
        with (
            client() as http,
            http.stream("GET", spec.url, headers=headers) as response,
        ):
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if content_type.startswith(
                "text/html"
            ) and not spec.filename.lower().endswith((".html", ".htm")):
                # Confirmed live (2026-08-07): a WAF in front of Census's
                # www2.census.gov occasionally answers a plain-data request
                # with HTTP 200 and an HTML "Request Rejected" page instead
                # of a real 404 or the actual file -- raise_for_status()
                # doesn't catch this since 200 isn't an error status. 13 ACS
                # Detailed Table files were silently accepted this way
                # across this session before this check existed (staged to
                # zero rows each, so no bad data reached a fact table, but
                # the artifact was wrongly marked "downloaded" and the real
                # table stayed missing). Treat it as a failed download so
                # the normal retry/resume path handles it instead.
                raise ValueError(
                    f"{spec.url} returned HTML content-type for a non-HTML artifact "
                    f"({spec.filename}) -- likely a WAF rejection page, not real data"
                )
            if existing and response.status_code != 206:
                existing, mode = 0, "wb"
            with partial.open(mode) as output:
                for chunk in response.iter_bytes(chunk_size):
                    output.write(chunk)
            digest = file_checksum(partial)
            target = _retain(spec, partial, digest, move=True)
            _upsert(
                spec,
                target,
                "downloaded",
                bytes=target.stat().st_size,
                checksum=digest,
                content_type=response.headers.get("content-type"),
            )
            return target
    except Exception as exc:
        _upsert(spec, target, "failed", error=str(exc))
        raise


def register_local(spec: ArtifactSpec, path: Path) -> Path:
    """Register a previously downloaded, immutable artifact without executing it."""
    if not path.is_file():
        raise FileNotFoundError(path)
    resolved = path.resolve()
    checksum = sha256()
    with resolved.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    retained = _retain(spec, resolved, checksum.hexdigest(), move=False)
    _upsert(
        spec,
        retained,
        "downloaded",
        bytes=resolved.stat().st_size,
        checksum=checksum.hexdigest(),
        content_type=guess_type(resolved.name)[0],
    )
    return retained


def approve_plan(path: Path, scope: dict[str, Any]) -> dict[str, Any]:
    """Approve one previewed bulk plan with an explicit canonical load scope."""
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("state") != "draft":
        raise ValueError(f"Plan must be in draft state, found {plan.get('state')!r}")
    preview_path = path.with_suffix(".preview.json")
    if not preview_path.is_file():
        raise ValueError(
            f"No preflight report for {path}; run the matching bulk-preview command first"
        )
    preview = json.loads(preview_path.read_text())
    if not preview.get("approved"):
        raise ValueError(
            f"Preflight did not approve {path}: {preview.get('reason', 'unknown reason')}"
        )
    plan["state"] = "approved"
    plan.setdefault("storage", {})["state"] = "previewed"
    plan["canonical_load_scope"] = scope
    plan["approval"] = {
        "approved_at": datetime.now(UTC).isoformat(),
        "preview_report": str(preview_path),
        "artifact_count": len(plan.get("artifacts", [])),
    }
    temp = path.with_suffix(".yaml.part")
    temp.write_text(yaml.safe_dump(plan, sort_keys=False))
    temp.replace(path)
    return plan


def download_plan(
    path: Path, update: Callable[[str], None] | None = None, *, workers: int = 1
) -> dict[str, Any]:
    """Download every approved plan artifact resumably and register checksums.

    ``workers`` > 1 downloads artifacts concurrently on a thread pool (this
    is network I/O, not CPU work, so threads -- not processes -- are the
    right tool). Each artifact still goes through the same `download()`
    call, including its own checksum/status bookkeeping, so partial
    progress under concurrency is exactly as resumable as the serial path.
    """
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("state") != "approved":
        raise ValueError(
            f"Plan must be approved before download, found {plan.get('state')!r}"
        )
    dataset_id = plan.get("dataset")
    if not isinstance(dataset_id, str):
        raise ValueError("Plan is missing a dataset ID")
    artifacts = plan.get("artifacts", [])
    if not artifacts:
        raise ValueError("Plan contains no artifacts")

    def _download_one(artifact: dict[str, Any]) -> tuple[str, str | None, str | None]:
        """Download one artifact, returning (artifact_key, path, error).

        Never raises -- a single artifact's transient failure (e.g. the WAF
        rejection page some Census hosts occasionally serve under load,
        which ``download()`` now detects and rejects) must not abort every
        other artifact's download in the same plan.
        """
        key, url, filename = (
            artifact.get("artifact_key"),
            artifact.get("url"),
            artifact.get("filename"),
        )
        if not all(isinstance(value, str) and value for value in (key, url, filename)):
            raise ValueError(f"Invalid artifact entry in {path}: {artifact!r}")
        if update:
            update(f"Downloading {key}")
        year = artifact.get("release_year")
        scoped_filename = f"{year}/{filename}" if year is not None else filename
        spec = ArtifactSpec(
            dataset_id=dataset_id,
            artifact_key=key,
            url=url,
            filename=scoped_filename,
            metadata={
                "plan": str(path),
                "kind": artifact.get("kind"),
                "release_year": year,
            },
        )
        try:
            return (key, str(download(spec)), None)
        except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
            return (key, None, str(exc))

    if workers <= 1:
        results = [_download_one(artifact) for artifact in artifacts]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_download_one, artifacts))
    downloaded = [path_ for _, path_, error in results if error is None]
    failed = {key: error for key, _, error in results if error is not None}
    if failed:
        raise RuntimeError(
            f"{len(failed)} of {len(artifacts)} artifacts failed to download "
            f"(succeeded ones are saved and will be skipped on retry): {failed}"
        )
    plan["state"] = "downloaded"
    plan["download"] = {
        "completed_at": datetime.now(UTC).isoformat(),
        "artifact_count": len(downloaded),
        "paths": downloaded,
    }
    temp = path.with_suffix(".yaml.part")
    temp.write_text(yaml.safe_dump(plan, sort_keys=False))
    temp.replace(path)
    return {
        "state": "downloaded",
        "plan": str(path),
        "artifact_count": len(downloaded),
        "paths": downloaded,
    }


def advance_plan(
    path: Path,
    expected_state: str,
    next_state: str,
    details_key: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    """Atomically record one completed bulk lifecycle phase in its plan."""
    plan = yaml.safe_load(path.read_text()) or {}
    if plan.get("state") != expected_state:
        raise ValueError(
            f"Plan must be {expected_state!r}, found {plan.get('state')!r}"
        )
    plan["state"] = next_state
    plan[details_key] = {"completed_at": datetime.now(UTC).isoformat(), **details}
    temp = path.with_suffix(".yaml.part")
    temp.write_text(yaml.safe_dump(plan, sort_keys=False))
    temp.replace(path)
    return plan
