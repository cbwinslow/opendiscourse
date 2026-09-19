"""Record what each ingest run wrote, per target table and coverage key.

Revision ID: c8e2a4f6d915
Revises: a3c7e9b1d254
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8e2a4f6d915"
down_revision: str | Sequence[str] | None = "a3c7e9b1d254"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VIEW = """
CREATE OR REPLACE VIEW ingest.loaded_coverage AS
SELECT DISTINCT ON (r.dataset_id, t.target, t.coverage_key)
       r.dataset_id, t.target, t.coverage_key, t.run_id, t.status,
       t.rows_inserted, t.rows_updated, t.rows_skipped,
       r.code_version, r.finished_at, t.recorded_at
FROM ingest.run_target t
JOIN ingest.run r ON r.run_id = t.run_id
WHERE t.status IN ('succeeded', 'partial')
ORDER BY r.dataset_id, t.target, t.coverage_key, t.recorded_at DESC
"""


def upgrade() -> None:
    """Create the ledger table and the 'what is loaded' view; old runs stay unattributed."""
    if sa.inspect(op.get_bind()).has_table("run_target", schema="ingest"):
        return
    op.create_table(
        "run_target",
        sa.Column(
            "run_target_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingest.run.run_id"), nullable=False
        ),
        sa.Column("target", sa.Text(), nullable=False),
        # '' means the whole target; never NULL so the unique key works.
        sa.Column("coverage_key", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("rows_inserted", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_updated", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("rows_skipped", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "status IN ('succeeded', 'partial', 'failed')", name="run_target_status_check"
        ),
        sa.CheckConstraint(
            "rows_inserted >= 0 AND rows_updated >= 0 AND rows_skipped >= 0",
            name="run_target_rows_check",
        ),
        sa.UniqueConstraint("run_id", "target", "coverage_key", name="run_target_run_key_unique"),
        schema="ingest",
    )
    op.create_index(
        "run_target_lookup_idx", "run_target", ["target", "coverage_key"], schema="ingest"
    )
    op.execute(_VIEW)


def downgrade() -> None:
    """Refuse to discard ledger history; it is the record of what each run wrote."""
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM ingest.run_target) THEN
            RAISE EXCEPTION 'refusing to drop ingest.run_target: it records what runs wrote';
          END IF;
        END $$
        """
    )
    op.execute("DROP VIEW IF EXISTS ingest.loaded_coverage")
    op.drop_table("run_target", schema="ingest")
