"""GovInfo BILLS text: lossless version records and typed version identity (Story 11.3).

Revision ID: f4a7c2e8b619
Revises: c8e2a5f1b937
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4a7c2e8b619"
down_revision: str | Sequence[str] | None = "c8e2a5f1b937"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)
_DOCUMENT_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("version_code", sa.Text()),
    ("congress", sa.Integer()),
    ("session", sa.Integer()),
    ("bill_type", sa.Text()),
    ("bill_number", sa.Text()),
    ("source_member", sa.Text()),
)


def _columns(table: str, schema: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table, schema=schema)}


def upgrade() -> None:
    """Expand only: nullable version-identity columns on document, plus the record table."""
    have = _columns("document", "core")
    for name, kind in _DOCUMENT_COLUMNS:
        if name not in have:
            op.add_column("document", sa.Column(name, kind), schema="core")
    op.create_index(
        "document_bill_version_idx",
        "document",
        ["congress", "bill_type", "bill_number", "version_code"],
        schema="core",
        unique=False,
        if_not_exists=True,
        postgresql_where=sa.text("version_code IS NOT NULL"),
    )
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("bill_text_source_record", schema="core"):
        op.create_table(
            "bill_text_source_record",
            sa.Column(
                "bill_text_source_record_id",
                _UUID,
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("bill_id", _UUID, sa.ForeignKey("core.bill.bill_id")),
            sa.Column(
                "source_artifact_id",
                _UUID,
                sa.ForeignKey("ingest.artifact.artifact_id"),
                nullable=False,
            ),
            sa.Column("source_member", sa.Text(), nullable=False),
            sa.Column("congress", sa.Integer(), nullable=False),
            sa.Column("session", sa.Integer(), nullable=False),
            sa.Column("bill_type", sa.Text(), nullable=False),
            sa.Column("bill_number", sa.Text(), nullable=False),
            sa.Column("version_code", sa.Text(), nullable=False),
            sa.Column("record", postgresql.JSONB(), nullable=False),
            sa.Column("record_sha256", sa.Text(), nullable=False),
            sa.Column(
                "loaded_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("source_artifact_id", "source_member"),
            schema="core",
        )
    op.create_index(
        "bill_text_source_record_bill_idx",
        "bill_text_source_record",
        ["bill_id"],
        schema="core",
        if_not_exists=True,
    )
    op.create_index(
        "bill_text_source_record_identity_idx",
        "bill_text_source_record",
        ["congress", "bill_type", "bill_number", "version_code"],
        schema="core",
        if_not_exists=True,
    )


def downgrade() -> None:
    """Refuse while loaded BILLS records exist: they are derived, but reloading them means a full new sync."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("bill_text_source_record", schema="core"):
        count = bind.execute(sa.text("SELECT count(*) FROM core.bill_text_source_record")).scalar_one()
        if count:
            raise RuntimeError(
                f"core.bill_text_source_record holds {count} rows; delete them "
                "(and re-sync later) before downgrading"
            )
        op.drop_index(
            "bill_text_source_record_identity_idx",
            table_name="bill_text_source_record",
            schema="core",
            if_exists=True,
        )
        op.drop_index(
            "bill_text_source_record_bill_idx",
            table_name="bill_text_source_record",
            schema="core",
            if_exists=True,
        )
        op.drop_table("bill_text_source_record", schema="core")
    op.drop_index("document_bill_version_idx", table_name="document", schema="core", if_exists=True)
    present = _columns("document", "core")
    for name, _ in reversed(_DOCUMENT_COLUMNS):
        if name in present:
            op.drop_column("document", name, schema="core")
