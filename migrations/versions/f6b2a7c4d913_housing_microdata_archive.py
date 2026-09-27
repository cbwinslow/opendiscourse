"""Add source-shaped ACS PUMS/AHS staging and release provenance.

Revision ID: f6b2a7c4d913
Revises: c9e4a1b27d83
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6b2a7c4d913"
down_revision: str | Sequence[str] | None = "c9e4a1b27d83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    """Create bounded source-shaped housing archive contracts.

    An old database without Alembic's watermark may already contain these
    tables (for example after a prior development install).  The project’s
    adoption path replays every revision, so this revision must safely stamp
    that existing, compatible schema instead of treating it as an error.
    """
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("acs_pums_record", schema="stage"):
        op.create_table(
            "acs_pums_record",
            sa.Column("artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id"), primary_key=True),
            sa.Column("source_member", sa.Text(), primary_key=True),
            sa.Column("source_ordinal", sa.BigInteger(), primary_key=True),
            sa.Column("product", sa.Text(), nullable=False),
            sa.Column("period", sa.Text(), nullable=False),
            sa.Column("record_type", sa.Text(), nullable=False),
            sa.Column("puma", sa.Text()),
            sa.Column("raw", postgresql.JSONB(), nullable=False),
            sa.CheckConstraint("product IN ('acs_pums_1', 'acs_pums_5')", name="acs_pums_product_check"),
            sa.CheckConstraint("record_type IN ('housing', 'person')", name="acs_pums_record_type_check"),
            schema="stage",
        )
    if not inspector.has_table("ahs_record", schema="stage"):
        op.create_table(
            "ahs_record",
            sa.Column("artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id"), primary_key=True),
            sa.Column("source_member", sa.Text(), primary_key=True),
            sa.Column("source_ordinal", sa.BigInteger(), primary_key=True),
            sa.Column("release_year", sa.Integer(), nullable=False),
            sa.Column("component", sa.Text(), nullable=False),
            sa.Column("table_name", sa.Text(), nullable=False),
            sa.Column("raw", postgresql.JSONB(), nullable=False),
            schema="stage",
        )
    if not inspector.has_table("housing_archive_release", schema="core"):
        op.create_table(
            "housing_archive_release",
            sa.Column("housing_archive_release_id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("dataset_id", sa.Text(), sa.ForeignKey("catalog.dataset.dataset_id"), nullable=False),
            sa.Column("product", sa.Text(), nullable=False),
            sa.Column("period", sa.Text(), nullable=False),
            sa.Column("component", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("source_artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id"), nullable=False),
            sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint("status IN ('standard', 'nonstandard', 'gap')", name="housing_archive_release_status_check"),
            sa.UniqueConstraint("dataset_id", "product", "period", "component", "source_artifact_id"),
            schema="core",
        )
    if not inspector.has_table("housing_microdata_projection", schema="core"):
        op.create_table(
            "housing_microdata_projection",
            sa.Column("artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id"), primary_key=True),
            sa.Column("source_member", sa.Text(), primary_key=True),
            sa.Column("source_ordinal", sa.BigInteger(), primary_key=True),
            sa.Column("product", sa.Text(), nullable=False),
            sa.Column("period", sa.Text(), nullable=False),
            sa.Column("component", sa.Text(), nullable=False),
            sa.Column("record_type", sa.Text(), nullable=False),
            sa.Column("puma", sa.Text()),
            sa.Column("weight", sa.Float()),
            sa.Column("age", sa.Integer()),
            sa.Column("sex", sa.Text()),
            sa.Column("race", sa.Text()),
            sa.Column("ethnicity", sa.Text()),
            sa.Column("income", sa.Numeric()),
            sa.Column("poverty_ratio", sa.Numeric()),
            sa.Column("education", sa.Text()),
            sa.Column("employment_status", sa.Text()),
            sa.Column("tenure", sa.Text()),
            sa.Column("rent", sa.Numeric()),
            sa.Column("gross_rent", sa.Numeric()),
            sa.Column("property_value", sa.Numeric()),
            sa.Column("year_built", sa.Integer()),
            sa.CheckConstraint("record_type IN ('housing', 'person', 'unit')", name="housing_projection_record_type_check"),
            schema="core",
        )


def downgrade() -> None:
    """Remove empty archive tables in reverse dependency order."""
    for schema, table in (("core", "housing_microdata_projection"), ("core", "housing_archive_release"), ("stage", "ahs_record"), ("stage", "acs_pums_record")):
        has_rows = op.get_bind().execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {schema}.{table})")).scalar()
        if has_rows:
            raise RuntimeError(f"refusing to downgrade non-empty {schema}.{table}")
        op.drop_table(table, schema=schema)
