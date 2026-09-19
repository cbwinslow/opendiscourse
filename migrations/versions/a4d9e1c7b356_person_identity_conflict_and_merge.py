"""Record identity conflicts and reviewed person merges (Story 10.1, ADR-0005).

Revision ID: a4d9e1c7b356
Revises: f3a8c5d1b7e2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4d9e1c7b356"
down_revision: str | Sequence[str] | None = "f3a8c5d1b7e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    """Expand only: three new tables, nothing existing is altered."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("identity_conflict", schema="ingest"):
        op.create_table(
            "identity_conflict",
            sa.Column("identity_conflict_id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("dataset_id", sa.Text(), sa.ForeignKey("catalog.dataset.dataset_id"), nullable=False),
            sa.Column("run_id", _UUID, sa.ForeignKey("ingest.run.run_id")),
            sa.Column("kind", sa.Text(), nullable=False),
            # The source record that asserted the identifiers, e.g. 'bioguide:S001188'.
            sa.Column("subject", sa.Text(), nullable=False),
            # Persons that own the asserted identifiers, sorted, so reruns hit one row.
            sa.Column("person_ids", postgresql.ARRAY(_UUID), nullable=False),
            sa.Column("identifiers", postgresql.JSONB(), nullable=False),
            sa.Column("seen_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("resolved_at", sa.DateTime(timezone=True)),
            sa.Column("resolution", sa.Text()),
            sa.CheckConstraint(
                "kind IN ('multiple_owners', 'bioguide_mismatch')", name="identity_conflict_kind_check"
            ),
            sa.UniqueConstraint("dataset_id", "kind", "subject", "person_ids", name="identity_conflict_key"),
            schema="ingest",
        )
    if not inspector.has_table("person_merge", schema="ingest"):
        op.create_table(
            "person_merge",
            sa.Column("person_merge_id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
            # One row per reviewed exception (inventory/identity_exceptions.yaml id).
            sa.Column("exception_id", sa.Text(), nullable=False, unique=True),
            sa.Column("survivor_person_id", _UUID, sa.ForeignKey("core.person.person_id"), nullable=False),
            # No foreign key: the duplicate is deleted by the merge.
            sa.Column("duplicate_person_id", _UUID, nullable=False),
            sa.Column("counts", postgresql.JSONB(), nullable=False),
            sa.Column("run_id", _UUID, sa.ForeignKey("ingest.run.run_id")),
            sa.Column("merged_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            schema="ingest",
        )
    if not inspector.has_table("person_merge_vote", schema="ingest"):
        op.create_table(
            "person_merge_vote",
            sa.Column("person_merge_id", _UUID, sa.ForeignKey("ingest.person_merge.person_merge_id"), nullable=False),
            sa.Column("roll_call_id", _UUID, nullable=False),
            # The duplicate's vote row exactly as it was, kept when the survivor already voted.
            sa.Column("vote", postgresql.JSONB(), nullable=False),
            sa.PrimaryKeyConstraint("person_merge_id", "roll_call_id"),
            schema="ingest",
        )


def downgrade() -> None:
    """Refuse when merges were recorded: the audit rows are the only copy of deleted votes."""
    bind = op.get_bind()
    for table in ("person_merge_vote", "person_merge", "identity_conflict"):
        if sa.inspect(bind).has_table(table, schema="ingest"):
            count = bind.execute(sa.text(f"SELECT count(*) FROM ingest.{table}")).scalar_one()
            if count:
                raise RuntimeError(f"ingest.{table} holds {count} rows; export them before downgrading")
    op.drop_table("person_merge_vote", schema="ingest", if_exists=True)
    op.drop_table("person_merge", schema="ingest", if_exists=True)
    op.drop_table("identity_conflict", schema="ingest", if_exists=True)
