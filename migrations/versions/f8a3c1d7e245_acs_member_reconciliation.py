"""Add parsed/existing/rejected member-reconciliation counters to the run ledger.

Revision ID: f8a3c1d7e245
Revises: f6b2a7c4d913
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a3c1d7e245"
down_revision: str | Sequence[str] | None = "f6b2a7c4d913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preserve existing run history while making member reconciliation explicit."""
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("run_target", schema="ingest")}
    for name in ("rows_parsed", "rows_existing", "rows_rejected"):
        if name not in columns:
            op.add_column(
                "run_target",
                sa.Column(name, sa.BigInteger(), nullable=False, server_default=sa.text("0")),
                schema="ingest",
            )
    op.drop_constraint("run_target_rows_check", "run_target", schema="ingest")
    op.create_check_constraint(
        "run_target_rows_check",
        "run_target",
        "rows_inserted >= 0 AND rows_updated >= 0 AND rows_skipped >= 0 "
        "AND rows_parsed >= 0 AND rows_existing >= 0 AND rows_rejected >= 0",
        schema="ingest",
    )


def downgrade() -> None:
    """Remove only empty/default reconciliation fields; run evidence is retained."""
    if op.get_bind().execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM ingest.run_target WHERE rows_parsed <> 0 OR rows_existing <> 0 OR rows_rejected <> 0)")
    ).scalar():
        raise RuntimeError("refusing to discard ACS member reconciliation evidence")
    op.drop_constraint("run_target_rows_check", "run_target", schema="ingest")
    op.create_check_constraint(
        "run_target_rows_check", "run_target",
        "rows_inserted >= 0 AND rows_updated >= 0 AND rows_skipped >= 0", schema="ingest",
    )
    for name in ("rows_rejected", "rows_existing", "rows_parsed"):
        op.drop_column("run_target", name, schema="ingest")
