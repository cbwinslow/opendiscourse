"""Typed SQLAlchemy contracts for canonical core and fact tables."""

from __future__ import annotations

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, REAL
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
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
    Index("measurement_lookup_idx", "dataset_id", "field_id", "period_start"),
    schema="fact",
)


def geography_table():
    """Return the Alembic-adopted canonical geography table."""
    return core_geography


def measurement_table():
    """Return the Alembic-adopted canonical measurement table."""
    return fact_measurement


core_geography_boundary = Table(
    "geography_boundary",
    SQLModel.metadata,
    Column("boundary_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("geography_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.geography.geography_id"), nullable=False),
    Column("boundary_vintage", Integer, nullable=False),
    Column("valid_from", Date),
    Column("valid_to", Date),
    Column("geom", Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    UniqueConstraint("geography_id", "boundary_vintage"),
    Index("geography_boundary_geom_idx", "geom", postgresql_using="gist"),
    schema="core",
)


def geography_boundary_table():
    """Return the Alembic-adopted canonical PostGIS boundary table."""
    return core_geography_boundary


core_jurisdiction = Table(
    "jurisdiction",
    SQLModel.metadata,
    Column("jurisdiction_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("classification", Text, nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    schema="core",
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
    CheckConstraint(
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        name="legislative_session_check",
    ),
    schema="core",
)


def jurisdiction_table():
    """Return the Alembic-adopted canonical jurisdiction table."""
    return core_jurisdiction


def legislative_session_table():
    """Return the Alembic-adopted canonical legislative-session table."""
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
    Index("bill_ocd_id_idx", "ocd_id", unique=True, postgresql_where=text("ocd_id IS NOT NULL")),
    schema="core",
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
    CheckConstraint(
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        name="bill_identifier_check",
    ),
    Index("bill_identifier_bill_idx", "bill_id"),
    schema="core",
)


def bill_table():
    """Return the Alembic-adopted canonical bill table."""
    return core_bill


def bill_identifier_table():
    """Return the Alembic-adopted bill-identifier provenance table."""
    return core_bill_identifier


core_person_identifier = Table(
    "person_identifier",
    SQLModel.metadata,
    Column("person_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.person.person_id"), nullable=False),
    Column("namespace", Text, primary_key=True),
    Column("external_id", Text, primary_key=True),
    Column("valid_from", Date),
    Column("valid_to", Date),
    schema="core",
)


core_person = Table(
    "person",
    SQLModel.metadata,
    Column("person_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("full_name", Text, nullable=False),
    Column("given_name", Text),
    Column("family_name", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    schema="core",
)


core_bill_action = Table(
    "bill_action",
    SQLModel.metadata,
    Column("bill_action_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("bill_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.bill.bill_id"), nullable=False),
    Column("action_date", DateTime(timezone=True)),
    Column("description", Text, nullable=False),
    Column("classification", ARRAY(Text)),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    Column("source_member", Text),
    Column("source_ordinal", Integer),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint(
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        name="bill_action_source_evidence",
    ),
    Index(
        "bill_action_source_member_idx",
        "bill_id",
        "source_artifact_id",
        "source_member",
        "source_ordinal",
        unique=True,
        postgresql_where=text("source_artifact_id IS NOT NULL"),
    ),
    schema="core",
)


core_bill_sponsorship = Table(
    "bill_sponsorship",
    SQLModel.metadata,
    Column("bill_sponsorship_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("bill_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.bill.bill_id"), nullable=False),
    Column("person_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.person.person_id")),
    Column("member_namespace", Text, nullable=False, server_default=text("'bioguide'")),
    Column("member_external_id", Text, nullable=False),
    Column("role", Text, nullable=False),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("source_member", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint(
        "role IN ('sponsor', 'cosponsor')", name="bill_sponsorship_role_check"
    ),
    CheckConstraint(
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        name="bill_sponsorship_check",
    ),
    UniqueConstraint(
        "bill_id",
        "member_namespace",
        "member_external_id",
        "role",
        "source_artifact_id",
        "source_member",
        postgresql_nulls_not_distinct=True,
    ),
    Index("bill_sponsorship_person_idx", "person_id"),
    schema="core",
)


core_bill_committee = Table(
    "bill_committee",
    SQLModel.metadata,
    Column("bill_committee_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("bill_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.bill.bill_id"), nullable=False),
    Column("namespace", Text, nullable=False, server_default=text("'congress.gov.committee'")),
    Column("external_id", Text, nullable=False),
    Column("name", Text),
    Column("chamber", Text),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("source_member", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint(
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        name="bill_committee_check",
    ),
    UniqueConstraint(
        "bill_id",
        "namespace",
        "external_id",
        "source_artifact_id",
        "source_member",
        postgresql_nulls_not_distinct=True,
    ),
    schema="core",
)


core_bill_subject = Table(
    "bill_subject",
    SQLModel.metadata,
    Column("bill_subject_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("bill_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.bill.bill_id"), nullable=False),
    Column("namespace", Text, nullable=False, server_default=text("'congress.gov.subject'")),
    Column("external_id", Text, nullable=False),
    Column("label", Text, nullable=False),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("source_member", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint(
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        name="bill_subject_check",
    ),
    UniqueConstraint(
        "bill_id",
        "namespace",
        "external_id",
        "source_artifact_id",
        "source_member",
        postgresql_nulls_not_distinct=True,
    ),
    schema="core",
)


core_document = Table(
    "document",
    SQLModel.metadata,
    Column("document_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("document_type", Text, nullable=False),
    Column("source_key", Text, nullable=False),
    Column("title", Text),
    Column("published_at", DateTime(timezone=True)),
    Column("language", Text, nullable=False, server_default=text("'en'")),
    Column("canonical_url", Text),
    Column("checksum_sha256", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("document_type", "source_key"),
    schema="core",
)


core_bill_document = Table(
    "bill_document",
    SQLModel.metadata,
    Column("bill_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.bill.bill_id"), primary_key=True),
    Column("document_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.document.document_id"), primary_key=True),
    Column("relation", Text, primary_key=True, server_default=text("'text'")),
    schema="core",
)


def person_identifier_table():
    """Return the Alembic-adopted canonical person-identifier table."""
    return core_person_identifier


def person_table():
    """Return the Alembic-adopted canonical people table."""
    return core_person


def bill_action_table():
    """Return the Alembic-adopted canonical bill-action table."""
    return core_bill_action


def bill_sponsorship_table():
    """Return the Alembic-adopted canonical bill-sponsorship table."""
    return core_bill_sponsorship


def bill_committee_table():
    """Return the Alembic-adopted canonical bill-committee table."""
    return core_bill_committee


def bill_subject_table():
    """Return the Alembic-adopted canonical bill-subject table."""
    return core_bill_subject


def document_table():
    """Return the Alembic-adopted canonical document table."""
    return core_document


def bill_document_table():
    """Return the Alembic-adopted canonical bill-document table."""
    return core_bill_document


core_organization = Table(
    "organization",
    SQLModel.metadata,
    Column("organization_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("organization_type", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("jurisdiction_geoid", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    schema="core",
)


core_organization_identifier = Table(
    "organization_identifier",
    SQLModel.metadata,
    Column(
        "organization_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.organization.organization_id"),
        nullable=False,
    ),
    Column("namespace", Text, primary_key=True),
    Column("external_id", Text, primary_key=True),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    schema="core",
)


core_membership = Table(
    "membership",
    SQLModel.metadata,
    Column(
        "membership_id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "person_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.person.person_id"),
        nullable=False,
    ),
    Column(
        "organization_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.organization.organization_id"),
        nullable=False,
    ),
    Column(
        "legislative_session_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.legislative_session.legislative_session_id"),
    ),
    Column("role", Text, nullable=False),
    Column("start_date", Date),
    Column("end_date", Date),
    Column(
        "source_artifact_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ingest.artifact.artifact_id"),
    ),
    Column(
        "source_payload_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ingest.raw_payload.payload_id"),
    ),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint(
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        name="membership_check",
    ),
    Index("membership_person_idx", "person_id"),
    Index("membership_organization_idx", "organization_id"),
    schema="core",
)


core_roll_call = Table(
    "roll_call",
    SQLModel.metadata,
    Column("roll_call_id", PostgreSQLUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("jurisdiction", Text, nullable=False),
    Column("legislative_session", Text, nullable=False),
    Column("chamber", Text),
    Column("external_id", Text, nullable=False),
    Column("occurred_at", DateTime(timezone=True)),
    Column("question", Text),
    Column("result", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("bill_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.bill.bill_id")),
    Column("legislative_session_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.legislative_session.legislative_session_id")),
    Column("organization_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.organization.organization_id")),
    Column("ocd_id", Text),
    UniqueConstraint("jurisdiction", "legislative_session", "external_id"),
    Index("roll_call_ocd_id_idx", "ocd_id", unique=True, postgresql_where=text("ocd_id IS NOT NULL")),
    schema="core",
)


fact_member_vote = Table(
    "member_vote",
    SQLModel.metadata,
    Column("roll_call_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.roll_call.roll_call_id"), primary_key=True),
    Column("person_id", PostgreSQLUUID(as_uuid=True), ForeignKey("core.person.person_id"), primary_key=True),
    Column("position", Text, nullable=False),
    Column("source_payload_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.raw_payload.payload_id")),
    Column("source_artifact_id", PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    CheckConstraint(
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        name="member_vote_source_evidence",
    ),
    schema="fact",
)


def organization_table():
    """Return the Alembic-adopted canonical organization table."""
    return core_organization


def organization_identifier_table():
    """Return Alembic-adopted stable organization identifiers."""
    return core_organization_identifier


def membership_table():
    """Return the Alembic-adopted canonical membership table."""
    return core_membership


def roll_call_table():
    """Return the Alembic-adopted canonical roll-call table."""
    return core_roll_call


def member_vote_table():
    """Return the Alembic-adopted canonical member-vote table."""
    return fact_member_vote


fact_population_estimate = Table(
    "population_estimate",
    SQLModel.metadata,
    Column(
        "population_estimate_id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("release_vintage", Integer, nullable=False),
    Column("estimate_year", Integer, nullable=False),
    Column(
        "geography_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.geography.geography_id"),
        nullable=False,
    ),
    Column("population", BigInteger, nullable=False),
    Column(
        "source_artifact_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ingest.artifact.artifact_id"),
        nullable=False,
    ),
    Column("source_member", Text, nullable=False),
    Column("source_ordinal", BigInteger, nullable=False),
    Column("loaded_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint(
        "source_artifact_id", "source_member", "source_ordinal", "estimate_year"
    ),
    Index("population_estimate_lookup_idx", "release_vintage", "estimate_year", "geography_id"),
    schema="fact",
)


def population_estimate_table():
    """Return the Alembic-adopted PEP population-estimate fact table."""
    return fact_population_estimate


fact_business_pattern = Table(
    "business_pattern",
    SQLModel.metadata,
    Column(
        "business_pattern_id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("release_year", Integer, nullable=False),
    Column(
        "geography_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.geography.geography_id"),
        nullable=False,
    ),
    Column("naics", Text, nullable=False),
    Column("legal_form", Text, nullable=False, server_default=text("''")),
    Column("establishments", BigInteger),
    Column("employment", BigInteger),
    Column("first_quarter_payroll", Numeric),
    Column("annual_payroll", Numeric),
    Column("flags", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column(
        "source_artifact_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ingest.artifact.artifact_id"),
        nullable=False,
    ),
    Column("source_member", Text, nullable=False),
    Column("source_ordinal", BigInteger, nullable=False),
    Column("loaded_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    UniqueConstraint("source_artifact_id", "source_member", "source_ordinal"),
    Index("business_pattern_lookup_idx", "release_year", "geography_id", "naics"),
    schema="fact",
)


def business_pattern_table():
    """Return the Alembic-adopted CBP business-pattern fact table."""
    return fact_business_pattern


fact_acs_bulk_estimate = Table(
    "acs_bulk_estimate",
    SQLModel.metadata,
    Column(
        "acs_bulk_estimate_id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("release_year", Integer, nullable=False),
    Column(
        "geography_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.geography.geography_id"),
        nullable=False,
    ),
    Column("table_id", Text, nullable=False),
    Column("field_id", Text, nullable=False),
    Column("measure", Text, nullable=False),
    Column("value", Numeric),
    Column(
        "source_artifact_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ingest.artifact.artifact_id"),
        nullable=False,
    ),
    Column("source_ordinal", BigInteger, nullable=False),
    CheckConstraint(
        "measure IN ('estimate', 'margin_of_error')",
        name="acs_bulk_estimate_measure_check",
    ),
    UniqueConstraint("source_artifact_id", "source_ordinal", "field_id"),
    Index(
        "acs_bulk_estimate_lookup_idx",
        "release_year",
        "geography_id",
        "table_id",
        "field_id",
    ),
    schema="fact",
)


def acs_bulk_estimate_table():
    """Return the Alembic-adopted ACS bulk-estimate fact table."""
    return fact_acs_bulk_estimate


fact_decennial_dhc_value = Table(
    "decennial_dhc_value",
    SQLModel.metadata,
    Column(
        "dhc_value_id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("release_year", Integer, nullable=False),
    Column(
        "geography_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.geography.geography_id"),
        nullable=False,
    ),
    Column("table_id", Text, nullable=False),
    Column("variable_id", Text, nullable=False),
    Column("value", BigInteger),
    Column(
        "source_artifact_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ingest.artifact.artifact_id"),
        nullable=False,
    ),
    Column("source_member", Text, nullable=False),
    Column("source_ordinal", BigInteger, nullable=False),
    UniqueConstraint(
        "source_artifact_id", "source_member", "source_ordinal", "variable_id"
    ),
    Index(
        "dhc_value_lookup_idx",
        "release_year",
        "geography_id",
        "table_id",
        "variable_id",
    ),
    schema="fact",
)


def decennial_dhc_value_table():
    """Return the Alembic-adopted decennial DHC value fact table."""
    return fact_decennial_dhc_value


core_instrument = Table(
    "instrument",
    SQLModel.metadata,
    Column(
        "instrument_id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("instrument_type", Text, nullable=False),
    Column("name", Text),
    Column("currency", Text),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    schema="core",
)


core_instrument_symbol = Table(
    "instrument_symbol",
    SQLModel.metadata,
    Column(
        "instrument_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.instrument.instrument_id"),
        nullable=False,
    ),
    Column("symbol", Text, primary_key=True),
    Column("exchange", Text, primary_key=True, server_default=text("''")),
    Column("valid_from", Date, primary_key=True, nullable=False),
    Column("valid_to", Date),
    schema="core",
)


fact_market_bar = Table(
    "market_bar",
    SQLModel.metadata,
    Column(
        "instrument_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.instrument.instrument_id"),
        primary_key=True,
    ),
    Column("trade_date", Date, primary_key=True),
    Column("interval", Text, primary_key=True, server_default=text("'1d'")),
    Column("open", Numeric),
    Column("high", Numeric),
    Column("low", Numeric),
    Column("close", Numeric),
    Column("adjusted_close", Numeric),
    Column("volume", Numeric),
    Column(
        "source_payload_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ingest.raw_payload.payload_id"),
        nullable=False,
    ),
    schema="fact",
)


def instrument_table():
    """Return the Alembic-adopted canonical financial-instrument table."""
    return core_instrument


def instrument_symbol_table():
    """Return Alembic-adopted stable instrument symbols."""
    return core_instrument_symbol


def market_bar_table():
    """Return the Alembic-adopted market-bar fact table."""
    return fact_market_bar


core_document_chunk = Table(
    "document_chunk",
    SQLModel.metadata,
    Column(
        "chunk_id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "document_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.document.document_id"),
        nullable=False,
    ),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("token_count", Integer),
    Column("checksum_sha256", Text, nullable=False),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    CheckConstraint("ordinal >= 0", name="document_chunk_ordinal_check"),
    UniqueConstraint("document_id", "ordinal"),
    UniqueConstraint("document_id", "checksum_sha256"),
    schema="core",
)


core_embedding = Table(
    "embedding",
    SQLModel.metadata,
    Column(
        "embedding_id",
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "chunk_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("core.document_chunk.chunk_id"),
        nullable=False,
    ),
    Column("model", Text, nullable=False),
    Column("dimensions", Integer, nullable=False),
    Column("vector_values", ARRAY(REAL), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint("dimensions > 0", name="embedding_dimensions_check"),
    CheckConstraint("cardinality(vector_values) = dimensions", name="embedding_check"),
    UniqueConstraint("chunk_id", "model"),
    schema="core",
)


def document_chunk_table():
    """Return the Alembic-adopted canonical document-chunk table."""
    return core_document_chunk


def embedding_table():
    """Return the Alembic-adopted portable embedding table."""
    return core_embedding
