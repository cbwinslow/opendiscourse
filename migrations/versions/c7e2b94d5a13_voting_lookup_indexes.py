"""Index a member's votes and a bill's roll calls (voting repair, R4).

``fact.member_vote`` was keyed by roll call first, so one member's history read the whole key: 4.4 s
on the live warehouse, 0.14 s with this index on a temporary copy. Both indexes are built
concurrently so a running sync is not blocked.

Revision ID: c7e2b94d5a13
Revises: a1d4c8e6f372
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "c7e2b94d5a13"
down_revision: str | Sequence[str] | None = "a1d4c8e6f372"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (index, schema, table, key columns, covering columns)
_INDEXES = (
    ("member_vote_person_idx", "fact", "member_vote", ("person_id", "roll_call_id"), ("position",)),
    ("roll_call_bill_idx", "core", "roll_call", ("bill_id",), ()),
)
_INVALID = sa.text(
    "SELECT 1 FROM pg_index i WHERE i.indexrelid = to_regclass(:name) AND NOT i.indisvalid"
)


def upgrade() -> None:
    """Build each index, first clearing the unusable remains of an interrupted concurrent build."""
    for name, schema, table, columns, include in _INDEXES:
        broken = not context.is_offline_mode() and bool(
            op.get_bind().execute(_INVALID, {"name": f"{schema}.{name}"}).scalar()
        )
        with op.get_context().autocommit_block():
            if broken:
                op.drop_index(name, table_name=table, schema=schema, postgresql_concurrently=True)
            op.create_index(
                name,
                table,
                list(columns),
                schema=schema,
                postgresql_include=list(include),
                postgresql_concurrently=True,
                if_not_exists=True,
            )


def downgrade() -> None:
    """Drop both indexes inside the migration transaction.

    Not concurrently: an older revision may refuse the downgrade, and that refusal must also bring
    these indexes back, because the recorded revision stays here.
    """
    for name, schema, table, _columns, _include in _INDEXES:
        op.drop_index(name, table_name=table, schema=schema, if_exists=True)
