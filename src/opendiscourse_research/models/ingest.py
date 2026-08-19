"""Typed references to legacy-owned ingestion evidence tables."""

from __future__ import annotations

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlmodel import SQLModel


ingest_cursor = SQLModel.metadata.tables.get("ingest.cursor")
if ingest_cursor is None:
    ingest_cursor = Table(
        "cursor",
        SQLModel.metadata,
        Column("plan_id", Text, ForeignKey("catalog.plan.plan_id"), primary_key=True),
        Column("cursor", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        Column(
            "successful_run_id",
            PostgreSQLUUID(as_uuid=True),
            ForeignKey("ingest.run.run_id"),
        ),
        Column(
            "updated_at",
            DateTime(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
        schema="ingest",
    )


def cursor_table():
    """Return the Alembic-adopted ingestion plan cursor table."""
    return ingest_cursor


ingest_run = SQLModel.metadata.tables.get("ingest.run")
if ingest_run is None:
    ingest_run = Table(
        "run",
        SQLModel.metadata,
        Column(
            "run_id",
            PostgreSQLUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        Column("dataset_id", Text, ForeignKey("catalog.dataset.dataset_id"), nullable=False),
        Column("mode", Text, nullable=False),
        Column("status", Text, nullable=False),
        Column(
            "started_at", DateTime(timezone=True), nullable=False, server_default=text("now()")
        ),
        Column("finished_at", DateTime(timezone=True)),
        Column("parameters", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        Column("record_count", BigInteger, nullable=False, server_default=text("0")),
        Column("error_message", Text),
        Column("code_version", Text),
        CheckConstraint(
            "mode IN ('backfill', 'incremental', 'manual')", name="run_mode_check"
        ),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'partial')",
            name="run_status_check",
        ),
        schema="ingest",
    )


ingest_raw_payload = SQLModel.metadata.tables.get("ingest.raw_payload")
if ingest_raw_payload is None:
    ingest_raw_payload = Table(
        "raw_payload",
        SQLModel.metadata,
        Column(
            "payload_id",
            PostgreSQLUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
        Column("run_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.run.run_id"), nullable=False),
        Column(
            "source_url", Text, nullable=False
        ),
        Column(
            "fetched_at", DateTime(timezone=True), nullable=False, server_default=text("now()")
        ),
        Column("http_status", Integer),
        Column("content_type", Text),
        Column("checksum_sha256", Text, nullable=False),
        Column("payload", JSONB, nullable=False),
        UniqueConstraint("run_id", "checksum_sha256"),
        Index("raw_payload_run_idx", "run_id"),
        schema="ingest",
    )


def run_table():
    """Return the Alembic-adopted ingestion run table."""
    return ingest_run


def raw_payload_table():
    """Return the Alembic-adopted immutable raw-provider payload table."""
    return ingest_raw_payload


ingest_resume_cursor = Table(
    "resume_cursor",
    SQLModel.metadata,
    Column("dataset_id", Text, ForeignKey("catalog.dataset.dataset_id"), primary_key=True),
    Column("cursor_key", Text, primary_key=True),
    Column("cursor", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    Column("last_run_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.run.run_id")),
    Column("state", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint(
        "state IN ('running', 'paused', 'complete')", name="resume_cursor_state_check"
    ),
    schema="ingest",
)


ingest_identity_exception = Table(
    "identity_exception",
    SQLModel.metadata,
    Column("identity_exception_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("dataset_id", Text, ForeignKey("catalog.dataset.dataset_id"), nullable=False),
    Column("run_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.run.run_id"), nullable=False),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id"), nullable=False),
    Column("congress", Integer, nullable=False),
    Column("kind", Text, nullable=False),
    Column("namespace", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("reference_count", Integer, nullable=False, server_default=text("1")),
    Column("first_seen_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Column("last_seen_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("kind IN ('voter')", name="identity_exception_kind_check"),
    CheckConstraint(
        "reference_count > 0", name="identity_exception_reference_count_check"
    ),
    UniqueConstraint("run_id", "kind", "namespace", "external_id", "reason"),
    Index("identity_exception_lookup_idx", "congress", "namespace", "external_id"),
    schema="ingest",
)


def resume_cursor_table():
    """Return Alembic-adopted OpenStates resume checkpoints."""
    return ingest_resume_cursor


def identity_exception_table():
    """Return Alembic-adopted unresolved identity exceptions."""
    return ingest_identity_exception
