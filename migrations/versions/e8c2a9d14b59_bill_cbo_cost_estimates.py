"""Promote CBO cost estimates retained in BILLSTATUS records.

Revision ID: e8c2a9d14b59
Revises: e7c2a9d14b58
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8c2a9d14b59"
down_revision: str | Sequence[str] | None = "e7c2a9d14b58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create and backfill the provenance-backed CBO child table for BILLSTATUS."""
    if not sa.inspect(op.get_bind()).has_table("bill_cbo_cost_estimate", schema="core"):
        op.create_table(
            "bill_cbo_cost_estimate",
            sa.Column(
                "bill_cbo_cost_estimate_id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("bill_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("core.bill.bill_id"), nullable=False),
            sa.Column(
                "source_artifact_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("ingest.artifact.artifact_id"),
                nullable=False,
            ),
            sa.Column("source_member", sa.Text(), nullable=False),
            sa.Column("source_ordinal", sa.Integer(), nullable=False),
            sa.Column("published_at", sa.DateTime(timezone=True)),
            sa.Column("title", sa.Text()),
            sa.Column("source_url", sa.Text()),
            sa.Column("description", sa.Text()),
            sa.UniqueConstraint("bill_id", "source_artifact_id", "source_member", "source_ordinal"),
            schema="core",
        )
    op.create_index(
        "bill_cbo_cost_estimate_published_at_idx",
        "bill_cbo_cost_estimate",
        ["published_at"],
        schema="core",
        if_not_exists=True,
    )
    _backfill(op.get_bind())


def _backfill(bind: sa.engine.Connection) -> None:
    """Promote CBO items from pre-existing, immutable BILLSTATUS record evidence."""
    bind.execute(
        sa.text(
            """
            INSERT INTO core.bill_cbo_cost_estimate (
              bill_id, source_artifact_id, source_member, source_ordinal,
              published_at, title, source_url, description
            )
            SELECT
              record.bill_id,
              record.source_artifact_id,
              record.source_member,
              item.ordinality,
              NULLIF(btrim(item.value ->> 'pubDate'), '')::timestamptz,
              NULLIF(btrim(item.value ->> 'title'), ''),
              NULLIF(btrim(item.value ->> 'url'), ''),
              NULLIF(btrim(item.value ->> 'description'), '')
            FROM core.bill_source_record AS record
            CROSS JOIN LATERAL jsonb_array_elements(
              CASE
                WHEN jsonb_typeof(record.record #> '{bill,cboCostEstimates,item}') = 'array'
                THEN record.record #> '{bill,cboCostEstimates,item}'
                ELSE '[]'::jsonb
              END
            ) WITH ORDINALITY AS item(value, ordinality)
            ON CONFLICT (bill_id, source_artifact_id, source_member, source_ordinal) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    """Drop the typed rows only after they have been deliberately cleared."""
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("bill_cbo_cost_estimate", schema="core"):
        return
    count = bind.execute(sa.text("SELECT count(*) FROM core.bill_cbo_cost_estimate")).scalar_one()
    if count:
        raise RuntimeError(
            "core.bill_cbo_cost_estimate holds "
            f"{count} rows; delete them (and re-sync later) before downgrading"
        )
    op.drop_index(
        "bill_cbo_cost_estimate_published_at_idx",
        table_name="bill_cbo_cost_estimate",
        schema="core",
        if_exists=True,
    )
    op.drop_table("bill_cbo_cost_estimate", schema="core")
