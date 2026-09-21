"""One BILLS version identity is one record, even across zip and fallback XML.

Revision ID: b8c4e2a17f03
Revises: f4a7c2e8b619
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8c4e2a17f03"
down_revision: str | Sequence[str] | None = "f4a7c2e8b619"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Replace the non-unique identity index with a unique one that includes session."""
    op.drop_index(
        "bill_text_source_record_identity_idx",
        table_name="bill_text_source_record",
        schema="core",
        if_exists=True,
    )
    op.create_index(
        "bill_text_source_record_identity_idx",
        "bill_text_source_record",
        ["congress", "session", "bill_type", "bill_number", "version_code"],
        unique=True,
        schema="core",
        if_not_exists=True,
    )


def downgrade() -> None:
    """Restore the original non-unique identity lookup (no session, not unique)."""
    op.drop_index(
        "bill_text_source_record_identity_idx",
        table_name="bill_text_source_record",
        schema="core",
        if_exists=True,
    )
    op.create_index(
        "bill_text_source_record_identity_idx",
        "bill_text_source_record",
        ["congress", "bill_type", "bill_number", "version_code"],
        schema="core",
        if_not_exists=True,
    )
