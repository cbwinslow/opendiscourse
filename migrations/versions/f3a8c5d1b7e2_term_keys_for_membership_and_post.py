"""Natural keys that make a legislator-term load idempotent (Story 3.3).

Revision ID: f3a8c5d1b7e2
Revises: e2b7d4a9c815
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3a8c5d1b7e2"
down_revision: str | Sequence[str] | None = "e2b7d4a9c815"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """One membership per person, chamber, role and start date; one post per place and label."""
    # Partial: rows asserted by a payload only (no artifact) are not term rows and stay unkeyed.
    op.create_index(
        "membership_term_key",
        "membership",
        ["person_id", "organization_id", "role", "start_date"],
        unique=True,
        schema="core",
        postgresql_where="source_artifact_id IS NOT NULL",
        if_not_exists=True,
    )
    op.create_index(
        "post_organization_division_label_key",
        "post",
        ["organization_id", "division_id", "label"],
        unique=True,
        schema="core",
        if_not_exists=True,
    )


def downgrade() -> None:
    """Drop the keys; the rows are derived from a retained artifact and can be reloaded."""
    op.drop_index("post_organization_division_label_key", table_name="post", schema="core", if_exists=True)
    op.drop_index("membership_term_key", table_name="membership", schema="core", if_exists=True)
