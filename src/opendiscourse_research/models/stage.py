"""Typed SQLAlchemy contracts for provider-specific bulk staging tables."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlmodel import SQLModel


def _artifact_column() -> Column:
    """Build the shared immutable artifact foreign-key column."""
    return Column(
        "artifact_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ingest.artifact.artifact_id"),
        primary_key=True,
    )


stage_cbp_row = Table(
    "cbp_row",
    SQLModel.metadata,
    _artifact_column(),
    Column("source_member", Text, primary_key=True),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("geography_level", Text, nullable=False),
    Column("raw", JSONB, nullable=False),
    Column("staged_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    schema="stage",
)


stage_pep_row = Table(
    "pep_row",
    SQLModel.metadata,
    _artifact_column(),
    Column("source_member", Text, primary_key=True),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("geography_level", Text, nullable=False),
    Column("raw", JSONB, nullable=False),
    Column("staged_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    schema="stage",
)


stage_tiger_feature = Table(
    "tiger_feature",
    SQLModel.metadata,
    _artifact_column(),
    Column("layer", Text, nullable=False),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("geoid", Text, nullable=False),
    Column("name", Text),
    Column("state_fips", Text),
    Column("county_fips", Text),
    Column("raw", JSONB, nullable=False),
    Column("geom", Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False),
    Column("staged_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Index("tiger_feature_geom_idx", "geom", postgresql_using="gist"),
    schema="stage",
)


stage_census_relationship_row = Table(
    "census_relationship_row",
    SQLModel.metadata,
    _artifact_column(),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("family", Text, nullable=False),
    Column("overlap_kind", Text, nullable=False),
    Column("district_geoid", Text),
    Column("overlap_geoid", Text),
    Column("area_land_part", BigInteger),
    Column("area_water_part", BigInteger),
    Column("raw", JSONB, nullable=False),
    Column("staged_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    schema="stage",
)


stage_census_block_assignment = Table(
    "census_block_assignment",
    SQLModel.metadata,
    _artifact_column(),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("family", Text, nullable=False),
    Column("block_geoid", Text, nullable=False),
    Column("district_code", Text, nullable=False),
    schema="stage",
)


stage_dhc_geo_row = Table(
    "dhc_geo_row",
    SQLModel.metadata,
    _artifact_column(),
    Column("source_member", Text, primary_key=True),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("logrecno", Text, nullable=False),
    Column("sumlev", Text, nullable=False),
    Column("geoid", Text),
    Column("raw", JSONB, nullable=False),
    Index("dhc_geo_lookup_idx", "artifact_id", "logrecno", "sumlev"),
    schema="stage",
)


stage_acs_bulk_row = Table(
    "acs_bulk_row",
    SQLModel.metadata,
    _artifact_column(),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("release_year", Integer, nullable=False),
    Column("table_id", Text, nullable=False),
    Column("geography_type", Text, nullable=False),
    Column("geoid", Text, nullable=False),
    Column("raw", JSONB, nullable=False),
    schema="stage",
)


stage_fec_row = Table(
    "fec_row",
    SQLModel.metadata,
    _artifact_column(),
    Column("family", Text, nullable=False),
    Column("cycle", SmallInteger, nullable=False),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("raw", JSONB, nullable=False),
    Column("staged_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    Index("fec_row_family_cycle_idx", "family", "cycle"),
    schema="stage",
)


# Housing microdata stays source-shaped in stage.  The typed publication layer
# can be expanded from these retained rows without reacquiring Census evidence.
stage_acs_pums_record = Table(
    "acs_pums_record",
    SQLModel.metadata,
    _artifact_column(),
    Column("source_member", Text, primary_key=True),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("product", Text, nullable=False),
    Column("period", Text, nullable=False),
    Column("record_type", Text, nullable=False),
    Column("puma", Text),
    Column("raw", JSONB, nullable=False),
    CheckConstraint("product IN ('acs_pums_1', 'acs_pums_5')", name="acs_pums_product_check"),
    CheckConstraint("record_type IN ('housing', 'person')", name="acs_pums_record_type_check"),
    schema="stage",
)

stage_ahs_record = Table(
    "ahs_record",
    SQLModel.metadata,
    _artifact_column(),
    Column("source_member", Text, primary_key=True),
    Column("source_ordinal", BigInteger, primary_key=True),
    Column("release_year", Integer, nullable=False),
    Column("component", Text, nullable=False),
    Column("table_name", Text, nullable=False),
    Column("raw", JSONB, nullable=False),
    schema="stage",
)
