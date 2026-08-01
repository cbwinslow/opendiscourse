from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from mimetypes import guess_type
from pathlib import Path
from typing import Iterator

import httpx
from psycopg.types.json import Jsonb

from ..config import settings
from ..db import connect
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
    path = data_root() / spec.dataset_id.replace('.', '/') / spec.filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _upsert(spec: ArtifactSpec, path: Path, status: str, **values: object) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO ingest.artifact (dataset_id, remote_url, local_path, artifact_key, period_start, period_end, status, metadata, bytes_downloaded, checksum_sha256, content_type, downloaded_at, error_message)
               VALUES (%(dataset_id)s, %(url)s, %(path)s, %(artifact_key)s, %(period_start)s, %(period_end)s, %(status)s, %(metadata)s, %(bytes)s, %(checksum)s, %(content_type)s,
                       CASE WHEN %(status)s = 'downloaded' THEN now() ELSE NULL END, %(error)s)
               ON CONFLICT (dataset_id, artifact_key) DO UPDATE SET
                 remote_url = EXCLUDED.remote_url, local_path = EXCLUDED.local_path, status = EXCLUDED.status,
                 bytes_downloaded = EXCLUDED.bytes_downloaded, checksum_sha256 = EXCLUDED.checksum_sha256,
                 content_type = EXCLUDED.content_type, downloaded_at = EXCLUDED.downloaded_at, error_message = EXCLUDED.error_message,
                 metadata = EXCLUDED.metadata""",
            {
                "dataset_id": spec.dataset_id, "url": spec.url, "path": str(path), "artifact_key": spec.artifact_key,
                "period_start": spec.period_start, "period_end": spec.period_end, "status": status,
                "metadata": Jsonb(spec.metadata or {}), "bytes": values.get("bytes"), "checksum": values.get("checksum"),
                "content_type": values.get("content_type"), "error": values.get("error"),
            },
        )
        conn.commit()


def download(spec: ArtifactSpec, *, overwrite: bool = False, chunk_size: int = 1024 * 1024) -> Path:
    """Atomically download an artifact and register its checksum/coverage state."""
    target, partial = artifact_path(spec), artifact_path(spec).with_suffix(artifact_path(spec).suffix + ".part")
    if target.exists() and not overwrite:
        digest = sha256(target.read_bytes()).hexdigest()
        _upsert(spec, target, "skipped", bytes=target.stat().st_size, checksum=digest)
        return target
    headers: dict[str, str] = {}
    mode = "wb"
    existing = partial.stat().st_size if partial.exists() else 0
    if existing:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"
    _upsert(spec, target, "downloading")
    try:
        with client() as http, http.stream("GET", spec.url, headers=headers) as response:
            response.raise_for_status()
            if existing and response.status_code != 206:
                existing, mode = 0, "wb"
            with partial.open(mode) as output:
                for chunk in response.iter_bytes(chunk_size):
                    output.write(chunk)
            partial.replace(target)
            digest = sha256(target.read_bytes()).hexdigest()
            _upsert(spec, target, "downloaded", bytes=target.stat().st_size, checksum=digest, content_type=response.headers.get("content-type"))
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
    _upsert(
        spec,
        resolved,
        "downloaded",
        bytes=resolved.stat().st_size,
        checksum=checksum.hexdigest(),
        content_type=guess_type(resolved.name)[0],
    )
    return resolved
