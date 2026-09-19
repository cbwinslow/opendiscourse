"""Read the artifact version that consumers should use.

``ingest.artifact`` keeps every version of a logical artifact. Consumers (loaders,
snapshots, health checks) almost never want "the newest row": a failed refresh
appends a checksum-less provisional version that must not hide verified bytes.
The rule lives once, in the ``ingest.current_artifact`` view; this module is the
only Python reader of it so a new consumer cannot reintroduce the bug.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Column, Date, Integer, Text, select, table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

from ..db import session
from ..models.catalog import artifact_table

# Mirrors the view filter in migration d9e4f1a7b632; a test keeps them equal.
CURRENT_STATUSES = ("downloaded", "skipped", "loaded")


def current_artifact_table():
    """Return a lightweight, read-only handle on ``ingest.current_artifact``."""
    return table(
        "current_artifact",
        Column("artifact_id", PostgreSQLUUID(as_uuid=True)),
        Column("dataset_id", Text),
        Column("remote_url", Text),
        Column("local_path", Text),
        Column("artifact_key", Text),
        Column("artifact_version", Integer),
        Column("period_start", Date),
        Column("period_end", Date),
        Column("status", Text),
        Column("checksum_sha256", Text),
        Column("bytes_downloaded", BigInteger),
        Column("metadata", JSONB),
        schema="ingest",
    )


def get_current_artifact(
    artifact_key: str, *, dataset_id: str | None = None
) -> dict[str, Any] | None:
    """Return the newest usable version of a logical artifact, or None."""
    view = current_artifact_table()
    statement = select(view).where(view.c.artifact_key == artifact_key)
    if dataset_id is not None:
        statement = statement.where(view.c.dataset_id == dataset_id)
    with session() as active_session:
        row = active_session.execute(statement.limit(1)).mappings().first()
    return dict(row) if row else None


def require_current_artifact(
    artifact_key: str, *, label: str, dataset_id: str | None = None
) -> dict[str, Any]:
    """Return the current version or raise the loaders' actionable error."""
    row = get_current_artifact(artifact_key, dataset_id=dataset_id)
    if row is None:
        raise ValueError(f"Required {label} artifact {artifact_key!r} has not been downloaded")
    return row


def report_artifacts(keys: list[str]) -> list[dict[str, Any]]:
    """Return one row per key: the current version, else the newest attempt.

    Health reporting must show a key whose only attempts failed (so it reads as
    failed, not missing) while never letting a failed refresh mask good bytes.
    """
    if not keys:
        return []
    view = current_artifact_table()
    base = artifact_table()
    with session() as active_session:
        rows = {
            row["artifact_key"]: dict(row)
            for row in active_session.execute(
                select(
                    view.c.artifact_id,
                    view.c.artifact_key,
                    view.c.status,
                    view.c.local_path,
                    view.c.bytes_downloaded,
                    view.c.checksum_sha256,
                ).where(view.c.artifact_key.in_(keys))
            ).mappings()
        }
        for row in active_session.execute(
            select(
                base.c.artifact_id,
                base.c.artifact_key,
                base.c.status,
                base.c.local_path,
                base.c.bytes_downloaded,
                base.c.checksum_sha256,
                base.c.error_message,
            )
            .where(base.c.artifact_key.in_(set(keys) - set(rows)))
            .order_by(base.c.artifact_key, base.c.artifact_version.desc())
        ).mappings():
            rows.setdefault(row["artifact_key"], dict(row))
    return list(rows.values())


def registered_local_paths() -> list[str]:
    """Every ``local_path`` the artifact registry refers to (all versions)."""
    base = artifact_table()
    with session() as active_session:
        return [
            row[0]
            for row in active_session.execute(
                select(base.c.local_path).where(base.c.local_path.is_not(None))
            )
        ]
