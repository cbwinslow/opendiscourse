"""nullable unique membership ocd_id

Revision ID: b8c2f1d4e390
Revises: c5e2d1a4f783
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c2f1d4e390"
down_revision: Union[str, Sequence[str], None] = "c5e2d1a4f783"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add dump membership OCD ids and allow membership identity exceptions."""
    op.add_column(
        "membership",
        sa.Column("ocd_id", sa.Text(), nullable=True),
        schema="core",
    )
    op.create_index(
        "membership_ocd_id_idx",
        "membership",
        ["ocd_id"],
        unique=True,
        schema="core",
        postgresql_where=sa.text("ocd_id IS NOT NULL"),
    )
    op.drop_constraint(
        "identity_exception_kind_check",
        "identity_exception",
        schema="ingest",
        type_="check",
    )
    op.create_check_constraint(
        "identity_exception_kind_check",
        "identity_exception",
        "kind IN ('voter', 'membership')",
        schema="ingest",
    )


def downgrade() -> None:
    """Remove membership OCD ids and restore voter-only identity exceptions."""
    op.execute(sa.text("DELETE FROM ingest.identity_exception WHERE kind = 'membership'"))
    op.drop_constraint(
        "identity_exception_kind_check",
        "identity_exception",
        schema="ingest",
        type_="check",
    )
    op.create_check_constraint(
        "identity_exception_kind_check",
        "identity_exception",
        "kind IN ('voter')",
        schema="ingest",
    )
    op.drop_index("membership_ocd_id_idx", table_name="membership", schema="core")
    op.drop_column("membership", "ocd_id", schema="core")
