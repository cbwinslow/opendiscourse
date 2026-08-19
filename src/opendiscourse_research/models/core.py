"""Typed references to legacy-owned core and fact tables used by shared ingestion."""

from __future__ import annotations

from sqlalchemy import Column, Date, ForeignKey, Numeric, Table, Text, UniqueConstraint, text
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
