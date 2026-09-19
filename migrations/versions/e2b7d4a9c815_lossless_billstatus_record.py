"""Store each BILLSTATUS file's full record, and promote summaries, laws, related bills, amendments.

Revision ID: e2b7d4a9c815
Revises: c8e2a4f6d915
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2b7d4a9c815"
down_revision: str | Sequence[str] | None = "c8e2a4f6d915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)
_TABLES = (
    "bill_amendment",
    "bill_related_bill",
    "bill_law",
    "bill_summary",
    "bill_source_record",
)


def _id(name: str) -> sa.Column:
    return sa.Column(name, _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _evidence(ordinal: bool = True) -> list[sa.Column]:
    columns = [
        sa.Column("bill_id", _UUID, sa.ForeignKey("core.bill.bill_id"), nullable=False),
        sa.Column(
            "source_artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id"), nullable=False
        ),
        sa.Column("source_member", sa.Text(), nullable=False),
    ]
    if ordinal:
        columns.append(sa.Column("source_ordinal", sa.Integer(), nullable=False))
    return columns


def _promoted_key() -> sa.UniqueConstraint:
    return sa.UniqueConstraint("bill_id", "source_artifact_id", "source_member", "source_ordinal")


def _create(name: str, *elements, indexes: Sequence[tuple[str, list[str]]] = ()) -> None:
    """Create ``core.<name>`` and its indexes unless a database adopted without a watermark has them."""
    if not sa.inspect(op.get_bind()).has_table(name, schema="core"):
        op.create_table(name, *elements, schema="core")
    for index_name, columns in indexes:
        op.create_index(index_name, name, columns, schema="core", if_not_exists=True)


def upgrade() -> None:
    """Create the record table and the four promoted tables (all keyed to their source artifact)."""
    _create(
        "bill_source_record",
        _id("bill_source_record_id"),
        *_evidence(ordinal=False),
        sa.Column("record", postgresql.JSONB(), nullable=False),
        sa.Column("record_sha256", sa.Text(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source_artifact_id", "source_member"),
        indexes=[("bill_source_record_bill_idx", ["bill_id"])],
    )
    _create(
        "bill_summary",
        _id("bill_summary_id"),
        *_evidence(),
        sa.Column("version_code", sa.Text()),
        sa.Column("action_date", sa.Date()),
        sa.Column("action_description", sa.Text()),
        sa.Column("update_date", sa.DateTime(timezone=True)),
        sa.Column("text", sa.Text()),
        _promoted_key(),
    )
    _create(
        "bill_law",
        _id("bill_law_id"),
        *_evidence(),
        sa.Column("law_type", sa.Text()),
        sa.Column("law_number", sa.Text(), nullable=False),
        _promoted_key(),
        indexes=[("bill_law_number_idx", ["law_number"])],
    )
    _create(
        "bill_related_bill",
        _id("bill_related_bill_id"),
        *_evidence(),
        sa.Column("related_congress", sa.Integer(), nullable=False),
        sa.Column("related_bill_type", sa.Text(), nullable=False),
        sa.Column("related_bill_number", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("latest_action_date", sa.Date()),
        sa.Column("latest_action_text", sa.Text()),
        sa.Column("relationships", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        _promoted_key(),
        indexes=[
            (
                "bill_related_bill_target_idx",
                ["related_congress", "related_bill_type", "related_bill_number"],
            )
        ],
    )
    _create(
        "bill_amendment",
        _id("bill_amendment_id"),
        *_evidence(),
        sa.Column("amendment_congress", sa.Integer(), nullable=False),
        sa.Column("amendment_type", sa.Text(), nullable=False),
        sa.Column("amendment_number", sa.Text(), nullable=False),
        sa.Column("chamber", sa.Text()),
        sa.Column("purpose", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("proposed_at", sa.DateTime(timezone=True)),
        sa.Column("update_date", sa.DateTime(timezone=True)),
        sa.Column("latest_action_date", sa.Date()),
        sa.Column("latest_action_text", sa.Text()),
        sa.Column("sponsor_bioguide_id", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        _promoted_key(),
        indexes=[
            ("bill_amendment_identity_idx", ["amendment_congress", "amendment_type", "amendment_number"]),
            ("bill_amendment_sponsor_idx", ["sponsor_bioguide_id"]),
        ],
    )


def downgrade() -> None:
    """Drop the tables; every row is derived from a retained artifact and can be reloaded."""
    for table in _TABLES:
        op.drop_table(table, schema="core")
