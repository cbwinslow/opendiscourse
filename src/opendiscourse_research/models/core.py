"""Typed references to legacy-owned core and fact tables used by shared ingestion."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, Table, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlmodel import SQLModel


core_geography = Table(
    "geography",
    SQLModel.metadata,
    Column("geography_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("geography_type", Text, nullable=False),
    Column("geoid", Text, nullable=False),
    Column("name", Text),
    Column("parent_geoid", Text),
    Column("state_fips", Text),
    Column("county_fips", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    UniqueConstraint("geography_type", "geoid"),
    schema="core",
    info={"alembic_exclude": True},
)


fact_measurement = Table(
    "measurement",
    SQLModel.metadata,
    Column("measurement_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("dataset_id", Text, ForeignKey("catalog.dataset.dataset_id"), nullable=False),
    Column("field_id", Text, nullable=False),
    Column("geography_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.geography.geography_id")),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date),
    Column("vintage_date", Date),
    Column("value_numeric", Numeric),
    Column("value_text", Text),
    Column("unit", Text),
    Column("margin_of_error", Numeric),
    Column("flags", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id"), nullable=False),
    UniqueConstraint(
        "dataset_id", "field_id", "geography_id", "period_start", "period_end", "vintage_date",
        postgresql_nulls_not_distinct=True,
    ),
    schema="fact",
    info={"alembic_exclude": True},
)


def geography_table():
    """Return legacy core geography storage without taking Alembic ownership."""
    return core_geography


def measurement_table():
    """Return legacy fact measurement storage without taking Alembic ownership."""
    return fact_measurement


core_geography_boundary = Table(
    "geography_boundary",
    SQLModel.metadata,
    Column("boundary_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("geography_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.geography.geography_id"), nullable=False),
    Column("boundary_vintage", Integer, nullable=False),
    Column("valid_from", Date),
    Column("valid_to", Date),
    Column("geom", Geometry("GEOMETRY", srid=4326), nullable=False),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    UniqueConstraint("geography_id", "boundary_vintage"),
    schema="core",
    info={"alembic_exclude": True},
)


def geography_boundary_table():
    """Return legacy PostGIS boundary storage without taking Alembic ownership."""
    return core_geography_boundary


core_jurisdiction = Table(
    "jurisdiction",
    SQLModel.metadata,
    Column("jurisdiction_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("classification", Text, nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    schema="core",
    info={"alembic_exclude": True},
)


core_legislative_session = Table(
    "legislative_session",
    SQLModel.metadata,
    Column("legislative_session_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("jurisdiction_id", Text, ForeignKey("core.jurisdiction.jurisdiction_id"), nullable=False),
    Column("identifier", Text, nullable=False),
    Column("name", Text),
    Column("classification", Text),
    Column("starts_on", Date),
    Column("ends_on", Date),
    Column("active", Boolean),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    UniqueConstraint("jurisdiction_id", "identifier"),
    schema="core",
    info={"alembic_exclude": True},
)


def jurisdiction_table():
    """Return legacy jurisdiction storage without taking Alembic ownership."""
    return core_jurisdiction


def legislative_session_table():
    """Return legacy legislative-session storage without taking Alembic ownership."""
    return core_legislative_session


core_bill = Table(
    "bill",
    SQLModel.metadata,
    Column("bill_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("jurisdiction", Text, nullable=False),
    Column("legislative_session", Text, nullable=False),
    Column("bill_type", Text, nullable=False),
    Column("bill_number", Text, nullable=False),
    Column("title", Text),
    Column("introduced_date", Date),
    Column("latest_action_date", Date),
    Column("latest_action", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("legislative_session_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.legislative_session.legislative_session_id")),
    Column("ocd_id", Text),
    UniqueConstraint("jurisdiction", "legislative_session", "bill_type", "bill_number"),
    schema="core",
    info={"alembic_exclude": True},
)


core_bill_identifier = Table(
    "bill_identifier",
    SQLModel.metadata,
    Column("bill_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.bill.bill_id"), nullable=False),
    Column("namespace", Text, primary_key=True),
    Column("external_id", Text, primary_key=True),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("source_url", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    schema="core",
    info={"alembic_exclude": True},
)


def bill_table():
    """Return legacy canonical bill storage without taking Alembic ownership."""
    return core_bill


def bill_identifier_table():
    """Return legacy bill identifier storage without taking Alembic ownership."""
    return core_bill_identifier
