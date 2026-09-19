"""Let a person identifier point at the artifact that asserted it.

Revision ID: a3c7e9b1d254
Revises: d9e4f1a7b632
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3c7e9b1d254"
down_revision: str | Sequence[str] | None = "d9e4f1a7b632"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable evidence; baseline rows predate it and stay NULL (ADR-0002 Class B)."""
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("person_identifier", schema="core")}
    if "source_artifact_id" not in columns:
        op.add_column(
            "person_identifier",
            sa.Column(
                "source_artifact_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("ingest.artifact.artifact_id"),
                nullable=True,
            ),
            schema="core",
        )
        op.create_index(
            "person_identifier_source_artifact_idx",
            "person_identifier",
            ["source_artifact_id"],
            schema="core",
        )


def downgrade() -> None:
    """Drop the pointer only; it holds no evidence of its own, artifacts stay."""
    op.drop_index(
        "person_identifier_source_artifact_idx", table_name="person_identifier", schema="core"
    )
    op.drop_column("person_identifier", "source_artifact_id", schema="core")
