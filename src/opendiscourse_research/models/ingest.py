"""Typed references to legacy-owned ingestion evidence tables."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlmodel import SQLModel


ingest_cursor = SQLModel.metadata.tables.get("ingest.cursor")
if ingest_cursor is None:
    ingest_cursor = Table(
        "cursor",
        SQLModel.metadata,
        Column("plan_id", Text, ForeignKey("catalog.plan.plan_id"), primary_key=True),
        Column("cursor", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        Column("successful_run_id", PostgreSQLUUID(as_uuid=True)),
        Column(
            "updated_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        schema="ingest",
        info={"alembic_exclude": True},
    )


def cursor_table():
    """Return the existing ingestion cursor table without taking Alembic ownership."""
    return ingest_cursor
