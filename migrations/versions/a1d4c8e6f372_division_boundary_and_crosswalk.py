"""Add ``core.division_boundary`` and ``core.geography_crosswalk`` (Story 10.3, ADR-0006).

Revision ID: a1d4c8e6f372
Revises: f8a3c1d7e245
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1d4c8e6f372"
down_revision: str | Sequence[str] | None = "f8a3c1d7e245"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WEIGHT_TYPES = "'none','assignment','population','housing_unit','household','employment','area','address_ratio'"


def _uuid_pk(name: str) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def upgrade() -> None:
    """Create the two expand-only tables; no existing table is rewritten.

    Each table is skipped when it already exists, as in the other adoption revisions, so a
    schema re-adopted after a partial drop converges instead of failing.
    """
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("division_boundary", schema="core"):
        _create_division_boundary()
    if not inspector.has_table("geography_crosswalk", schema="core"):
        _create_geography_crosswalk()


def _create_division_boundary() -> None:
    op.create_table(
        "division_boundary",
        _uuid_pk("division_boundary_id"),
        sa.Column("division_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.division.division_id"), nullable=False),
        sa.Column(
            "boundary_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.geography_boundary.boundary_id"), nullable=False
        ),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("congress", sa.Integer()),
        sa.Column("legislative_year", sa.Integer()),
        sa.Column("relationship_kind", sa.Text(), nullable=False),
        sa.Column(
            "source_artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingest.artifact.artifact_id"), nullable=False
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("division_id", "boundary_id", name="division_boundary_pair_key"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_from < valid_to", name="division_boundary_validity_check"
        ),
        schema="core",
    )
    op.create_index(
        "division_boundary_division_validity_idx", "division_boundary", ["division_id", "valid_from", "valid_to"], schema="core"
    )
    op.create_index("division_boundary_boundary_idx", "division_boundary", ["boundary_id"], schema="core")
    op.create_index(
        "division_boundary_congress_idx",
        "division_boundary",
        ["congress"],
        schema="core",
        postgresql_where=sa.text("congress IS NOT NULL"),
    )



def _create_geography_crosswalk() -> None:
    op.create_table(
        "geography_crosswalk",
        _uuid_pk("geography_crosswalk_id"),
        sa.Column("from_geography_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.geography.geography_id"), nullable=False),
        sa.Column("to_geography_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.geography.geography_id"), nullable=False),
        sa.Column("from_vintage", sa.Integer(), nullable=False),
        sa.Column("to_vintage", sa.Integer(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("weight_type", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float()),
        sa.Column("numerator", sa.Float()),
        sa.Column("denominator", sa.Float()),
        sa.Column("coverage_ratio", sa.Float()),
        sa.Column("quality_flag", sa.Text()),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("source_dataset_id", sa.Text(), sa.ForeignKey("catalog.dataset.dataset_id"), nullable=False),
        sa.Column(
            "source_artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingest.artifact.artifact_id"), nullable=False
        ),
        sa.Column("source_ordinal", sa.BigInteger()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(f"weight_type IN ({_WEIGHT_TYPES})", name="geography_crosswalk_weight_type_check"),
        sa.CheckConstraint(
            "(weight_type = 'none' AND weight IS NULL) OR (weight_type <> 'none' AND weight IS NOT NULL)",
            name="geography_crosswalk_weight_presence_check",
        ),
        sa.CheckConstraint("weight IS NULL OR (weight >= 0 AND weight <= 1)", name="geography_crosswalk_weight_range_check"),
        sa.CheckConstraint(
            "coverage_ratio IS NULL OR (coverage_ratio >= 0 AND coverage_ratio <= 1)",
            name="geography_crosswalk_coverage_ratio_range_check",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_from < valid_to", name="geography_crosswalk_validity_check"
        ),
        sa.UniqueConstraint(
            "from_geography_id",
            "to_geography_id",
            "from_vintage",
            "to_vintage",
            "method",
            "weight_type",
            "source_artifact_id",
            "source_ordinal",
            name="geography_crosswalk_source_key",
            postgresql_nulls_not_distinct=True,
        ),
        schema="core",
    )
    op.create_index("geography_crosswalk_from_idx", "geography_crosswalk", ["from_geography_id", "from_vintage"], schema="core")
    op.create_index("geography_crosswalk_to_idx", "geography_crosswalk", ["to_geography_id", "to_vintage"], schema="core")


def downgrade() -> None:
    """Drop only these tables, and only while empty: linked evidence is never discarded."""
    bind = op.get_bind()
    for table in ("geography_crosswalk", "division_boundary"):
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM core.{table})")).scalar():
            raise RuntimeError(f"refusing to drop populated core.{table}; its rows are district evidence")
    op.drop_table("geography_crosswalk", schema="core")
    op.drop_table("division_boundary", schema="core")
