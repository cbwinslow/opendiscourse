"""Read the ingest run ledger: what is loaded, by dataset, target and coverage key."""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, Column, DateTime, Text, select, table
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

from ..db import session


def loaded_coverage_table():
    """Lightweight read-only handle on the ``ingest.loaded_coverage`` view."""
    return table(
        "loaded_coverage",
        Column("dataset_id", Text),
        Column("target", Text),
        Column("coverage_key", Text),
        Column("run_id", PostgreSQLUUID(as_uuid=True)),
        Column("status", Text),
        Column("rows_inserted", BigInteger),
        Column("rows_updated", BigInteger),
        Column("rows_skipped", BigInteger),
        Column("code_version", Text),
        Column("finished_at", DateTime(timezone=True)),
        Column("recorded_at", DateTime(timezone=True)),
        schema="ingest",
    )


def loaded_coverage(dataset_id: str | None = None) -> list[dict[str, Any]]:
    """Newest successful (or partial) record per dataset, target and coverage key."""
    view = loaded_coverage_table()
    statement = select(view).order_by(view.c.dataset_id, view.c.target, view.c.coverage_key)
    if dataset_id is not None:
        statement = statement.where(view.c.dataset_id == dataset_id)
    with session() as active_session:
        return [dict(row) for row in active_session.execute(statement).mappings()]
