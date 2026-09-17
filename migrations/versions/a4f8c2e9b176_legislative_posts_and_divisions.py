"""legislative posts and divisions

Revision ID: a4f8c2e9b176
Revises: c4f7a2d9e651
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a4f8c2e9b176"
down_revision: Union[str, Sequence[str], None] = "c4f7a2d9e651"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add owned political divisions, organization posts, and nullable membership.post_id."""
    op.create_table(
        "division",
        sa.Column(
            "division_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("ocd_division_id", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("classification", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_payload_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
            name="division_check",
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["ingest.artifact.artifact_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_payload_id"],
            ["ingest.raw_payload.payload_id"],
        ),
        sa.PrimaryKeyConstraint("division_id"),
        schema="core",
    )
    op.create_index(
        "division_ocd_division_id_idx",
        "division",
        ["ocd_division_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("ocd_division_id IS NOT NULL"),
    )
    op.create_table(
        "post",
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("division_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ocd_id", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_payload_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
            name="post_check",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["core.organization.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["division_id"],
            ["core.division.division_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["ingest.artifact.artifact_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_payload_id"],
            ["ingest.raw_payload.payload_id"],
        ),
        sa.PrimaryKeyConstraint("post_id"),
        sa.UniqueConstraint(
            "post_id", "organization_id", name="post_id_organization_id_key"
        ),
        schema="core",
    )
    op.create_index(
        "post_organization_idx",
        "post",
        ["organization_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "post_division_idx",
        "post",
        ["division_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        "post_ocd_id_idx",
        "post",
        ["ocd_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("ocd_id IS NOT NULL"),
    )
    op.add_column(
        "membership",
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="core",
    )
    op.create_foreign_key(
        "membership_post_organization_fkey",
        "membership",
        "post",
        ["post_id", "organization_id"],
        ["post_id", "organization_id"],
        source_schema="core",
        referent_schema="core",
    )
    op.create_index(
        "membership_post_idx",
        "membership",
        ["post_id"],
        unique=False,
        schema="core",
    )


def downgrade() -> None:
    """Remove legislative posts and divisions without rewriting remaining memberships."""
    op.drop_index("membership_post_idx", table_name="membership", schema="core")
    op.drop_constraint(
        "membership_post_organization_fkey",
        "membership",
        schema="core",
        type_="foreignkey",
    )
    op.drop_column("membership", "post_id", schema="core")
    op.drop_index("post_ocd_id_idx", table_name="post", schema="core")
    op.drop_index("post_division_idx", table_name="post", schema="core")
    op.drop_index("post_organization_idx", table_name="post", schema="core")
    op.drop_table("post", schema="core")
    op.drop_index("division_ocd_division_id_idx", table_name="division", schema="core")
    op.drop_table("division", schema="core")
