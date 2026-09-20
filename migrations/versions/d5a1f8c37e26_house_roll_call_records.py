"""House roll calls from the Clerk's XML: whole record, typed header, party totals, vote detail (Story 11.1).

Revision ID: d5a1f8c37e26
Revises: b7e4c2a19d63
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5a1f8c37e26"
down_revision: str | Sequence[str] | None = "b7e4c2a19d63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)

# Nullable and unindexed: existing rows (OpenStates-derived) keep working and are enriched on load.
ROLL_CALL_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("roll_number", sa.Integer()),
    ("roll_year", sa.Integer()),
    ("congress_session", sa.Text()),
    ("legislative_number", sa.Text()),
    ("vote_type", sa.Text()),
    ("vote_result", sa.Text()),
    ("majority_party", sa.Text()),
    ("vote_description", sa.Text()),
    ("amendment_number", sa.Text()),
    ("amendment_author", sa.Text()),
    ("action_date", sa.Date()),
    ("action_time_etz", sa.Text()),
    ("yea_total", sa.Integer()),
    ("nay_total", sa.Integer()),
    ("present_total", sa.Integer()),
    ("not_voting_total", sa.Integer()),
)
MEMBER_VOTE_COLUMNS: tuple[str, ...] = (
    "position_raw",
    "party_at_vote",
    "state_at_vote",
    "name_at_vote",
    "sort_name_at_vote",
    "unaccented_name_at_vote",
    "role_at_vote",
)


def _columns(table: str, schema: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table, schema=schema)}


def upgrade() -> None:
    """Expand only: new nullable columns and two new tables."""
    inspector = sa.inspect(op.get_bind())
    have = _columns("roll_call", "core")
    for name, kind in ROLL_CALL_COLUMNS:
        if name not in have:
            op.add_column("roll_call", sa.Column(name, kind), schema="core")
    if "source_artifact_id" not in have:
        op.add_column(
            "roll_call",
            sa.Column("source_artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id")),
            schema="core",
        )
    have = _columns("member_vote", "fact")
    for name in MEMBER_VOTE_COLUMNS:
        if name not in have:
            op.add_column("member_vote", sa.Column(name, sa.Text()), schema="fact")

    if not inspector.has_table("roll_call_source_record", schema="core"):
        op.create_table(
            "roll_call_source_record",
            sa.Column(
                "roll_call_source_record_id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
            ),
            sa.Column("roll_call_id", _UUID, sa.ForeignKey("core.roll_call.roll_call_id"), nullable=False),
            # One file, one artifact, one record: a refreshed file is a new artifact version.
            sa.Column("source_artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id"), nullable=False),
            sa.Column("record", postgresql.JSONB(), nullable=False),
            sa.Column("record_sha256", sa.Text(), nullable=False),
            # What the file said that the typed rows could not take, so a rerun neither loses nor forgets it.
            sa.Column("entry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("typed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("entries_without_id", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column(
                "unresolved_bioguide_ids",
                postgresql.ARRAY(sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::text[]"),
            ),
            sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("source_artifact_id"),
            schema="core",
        )
        op.create_index("roll_call_source_record_roll_idx", "roll_call_source_record", ["roll_call_id"], schema="core")
    if not inspector.has_table("roll_call_party_total", schema="core"):
        op.create_table(
            "roll_call_party_total",
            sa.Column("roll_call_id", _UUID, sa.ForeignKey("core.roll_call.roll_call_id"), primary_key=True),
            sa.Column("party", sa.Text(), primary_key=True),
            sa.Column("yea_total", sa.Integer()),
            sa.Column("nay_total", sa.Integer()),
            sa.Column("present_total", sa.Integer()),
            sa.Column("not_voting_total", sa.Integer()),
            sa.Column("source_artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id"), nullable=False),
            schema="core",
        )


def downgrade() -> None:
    """Refuse while official rows exist: they are derived, but reloading them means a full new sync."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("roll_call_source_record", schema="core"):
        count = bind.execute(sa.text("SELECT count(*) FROM core.roll_call_source_record")).scalar_one()
        if count:
            raise RuntimeError(
                f"core.roll_call_source_record holds {count} rows; delete them (and re-sync later) before downgrading"
            )
    if "position_raw" in _columns("member_vote", "fact"):
        count = bind.execute(sa.text("SELECT count(*) FROM fact.member_vote WHERE position_raw IS NOT NULL")).scalar_one()
        if count:
            raise RuntimeError(f"{count} fact.member_vote rows carry official detail; clear it before downgrading")
    op.drop_table("roll_call_party_total", schema="core", if_exists=True)
    op.drop_table("roll_call_source_record", schema="core", if_exists=True)
    for name in MEMBER_VOTE_COLUMNS:
        op.execute(f"ALTER TABLE fact.member_vote DROP COLUMN IF EXISTS {name}")
    op.execute("ALTER TABLE core.roll_call DROP COLUMN IF EXISTS source_artifact_id")
    for name, _ in ROLL_CALL_COLUMNS:
        op.execute(f"ALTER TABLE core.roll_call DROP COLUMN IF EXISTS {name}")
