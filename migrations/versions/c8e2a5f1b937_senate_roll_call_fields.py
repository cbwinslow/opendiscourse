"""Senate roll calls from senate.gov XML: document, amendment, tie-breaker and per-senator fields (Story 11.2).

Revision ID: c8e2a5f1b937
Revises: d5a1f8c37e26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e2a5f1b937"
down_revision: str | Sequence[str] | None = "d5a1f8c37e26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Nullable and unindexed, like the House columns of Story 11.1: existing rows keep working and are
# enriched on load. The House's shared columns (question, vote_result, amendment_number, the counts,
# action_date and time) are reused; these are the fields only the Senate file has.
ROLL_CALL_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("vote_question_text", sa.Text()),
    ("vote_document_text", sa.Text()),
    ("vote_result_text", sa.Text()),
    ("vote_title", sa.Text()),
    ("majority_requirement", sa.Text()),
    ("modified_at", sa.DateTime(timezone=True)),
    ("document_congress", sa.Integer()),
    ("document_type", sa.Text()),
    ("document_number", sa.Text()),
    ("document_name", sa.Text()),
    ("document_title", sa.Text()),
    ("document_short_title", sa.Text()),
    ("amendment_to_amendment_number", sa.Text()),
    ("amendment_to_amendment_to_amendment_number", sa.Text()),
    ("amendment_to_document_number", sa.Text()),
    ("amendment_to_document_short_title", sa.Text()),
    ("amendment_purpose", sa.Text()),
    ("tie_breaker_by", sa.Text()),
    ("tie_breaker_vote", sa.Text()),
)
MEMBER_VOTE_COLUMNS: tuple[str, ...] = ("last_name_at_vote", "first_name_at_vote", "lis_member_id_at_vote")
UNRESOLVED_COMMENT = (
    "Ids of the file's entries the warehouse could not resolve: BioGuide ids for the House, LIS member ids "
    "(or a marker for an entry with no id) for the Senate. A rerun tries them again."
)


def _columns(table: str, schema: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table, schema=schema)}


def upgrade() -> None:
    """Expand only: new nullable columns."""
    have = _columns("roll_call", "core")
    for name, kind in ROLL_CALL_COLUMNS:
        if name not in have:
            op.add_column("roll_call", sa.Column(name, kind), schema="core")
    have = _columns("member_vote", "fact")
    for name in MEMBER_VOTE_COLUMNS:
        if name not in have:
            op.add_column("member_vote", sa.Column(name, sa.Text()), schema="fact")
    op.execute(
        "COMMENT ON COLUMN core.roll_call_source_record.unresolved_bioguide_ids IS '"
        + UNRESOLVED_COMMENT.replace("'", "''")
        + "'"
    )


def downgrade() -> None:
    """Refuse while Senate detail exists: it is derived, but reloading it means a full new sync.

    Any Senate source record, any Senate-only roll-call column holding data, or any Senate-only vote
    column holding data blocks it (an OpenStates row enriched from a file may have no vote title).
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("roll_call_source_record", schema="core"):
        count = bind.execute(
            sa.text(
                "SELECT count(*) FROM core.roll_call_source_record s JOIN ingest.artifact a "
                "ON a.artifact_id = s.source_artifact_id WHERE a.dataset_id = 'congress.senate_votes'"
            )
        ).scalar_one()
        if count:
            raise RuntimeError(f"{count} Senate rows in core.roll_call_source_record; clear them before downgrading")
    present = _columns("roll_call", "core")
    used = " OR ".join(f"{name} IS NOT NULL" for name, _ in ROLL_CALL_COLUMNS if name in present)
    if used:
        count = bind.execute(sa.text(f"SELECT count(*) FROM core.roll_call WHERE {used}")).scalar_one()
        if count:
            raise RuntimeError(f"{count} core.roll_call rows carry Senate detail; clear it before downgrading")
    present = _columns("member_vote", "fact")
    used = " OR ".join(f"{name} IS NOT NULL" for name in MEMBER_VOTE_COLUMNS if name in present)
    if used:
        count = bind.execute(sa.text(f"SELECT count(*) FROM fact.member_vote WHERE {used}")).scalar_one()
        if count:
            raise RuntimeError(f"{count} fact.member_vote rows carry Senate detail; clear it before downgrading")
    op.execute("COMMENT ON COLUMN core.roll_call_source_record.unresolved_bioguide_ids IS NULL")
    for name in MEMBER_VOTE_COLUMNS:
        op.execute(f"ALTER TABLE fact.member_vote DROP COLUMN IF EXISTS {name}")
    for name, _ in ROLL_CALL_COLUMNS:
        op.execute(f"ALTER TABLE core.roll_call DROP COLUMN IF EXISTS {name}")
