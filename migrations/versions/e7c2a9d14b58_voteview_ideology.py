"""Voteview ideology and roll-call index.

Revision ID: e7c2a9d14b58
Revises: c4e8a1b93d27

Expand only. Scores stay Voteview's measurements. ``voteview`` is a person-name
kind that is ranked and never displayed. Downgrade refuses while the new tables
or voteview name notes still have rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7c2a9d14b58"
down_revision: str | Sequence[str] | None = "c4e8a1b93d27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)
_PERSON_KIND = "name_kind IN ('official', 'common', 'roster', 'voteview')"
_PERSON_KIND_PRIOR = "name_kind IN ('official', 'common', 'roster')"
_PRECEDENCE_SCOPE = (
    "(entity = 'person' AND name_kind IN ('official', 'common', 'roster', 'voteview') "
    "AND geography_type = '') "
    "OR (entity = 'geography' AND name_kind IN ('short', 'full') AND geography_type <> '')"
)
_PRECEDENCE_SCOPE_PRIOR = (
    "(entity = 'person' AND name_kind IN ('official', 'common', 'roster') AND geography_type = '') "
    "OR (entity = 'geography' AND name_kind IN ('short', 'full') AND geography_type <> '')"
)


def upgrade() -> None:
    """Add the Voteview tables and allow the voteview name kind."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("voteview_member", schema="core"):
        _create_member()
    if not inspector.has_table("voteview_roll_call", schema="core"):
        _create_roll_call()
    if not inspector.has_table("voteview_party", schema="core"):
        _create_party()
    _widen_name_kinds()


def _evidence() -> list[sa.Column]:
    return [
        sa.Column(
            "source_artifact_id",
            _UUID,
            sa.ForeignKey("ingest.artifact.artifact_id"),
            nullable=False,
        ),
        sa.Column("run_id", _UUID, sa.ForeignKey("ingest.run.run_id"), nullable=False),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def _create_member() -> None:
    op.create_table(
        "voteview_member",
        sa.Column(
            "voteview_member_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("congress", sa.Integer(), nullable=False),
        sa.Column("chamber", sa.Text(), nullable=False),
        sa.Column("icpsr", sa.Text(), nullable=False),
        sa.Column("state_icpsr", sa.Integer()),
        sa.Column("district_code", sa.Integer()),
        sa.Column("state_abbrev", sa.Text()),
        sa.Column("party_code", sa.Integer(), nullable=False),
        sa.Column("occupancy", sa.Integer()),
        sa.Column("last_means", sa.Integer()),
        sa.Column("bioname", sa.Text(), nullable=False),
        sa.Column("bioguide", sa.Text()),
        sa.Column("born", sa.Float()),
        sa.Column("died", sa.Float()),
        sa.Column("nominate_dim1", sa.Float()),
        sa.Column("nominate_dim2", sa.Float()),
        sa.Column("nominate_log_likelihood", sa.Float()),
        sa.Column("nominate_geo_mean_probability", sa.Float()),
        sa.Column("nominate_number_of_votes", sa.Integer()),
        sa.Column("nominate_number_of_errors", sa.Integer()),
        sa.Column("conditional", sa.Text()),
        sa.Column("nokken_poole_dim1", sa.Float()),
        sa.Column("nokken_poole_dim2", sa.Float()),
        sa.Column("person_id", _UUID, sa.ForeignKey("core.person.person_id")),
        sa.Column("record", postgresql.JSONB(), nullable=False),
        *_evidence(),
        sa.CheckConstraint("congress > 0", name="voteview_member_congress_check"),
        sa.CheckConstraint(
            "chamber IN ('house', 'senate', 'president')",
            name="voteview_member_chamber_check",
        ),
        sa.CheckConstraint("btrim(icpsr) <> ''", name="voteview_member_icpsr_check"),
        sa.CheckConstraint("btrim(bioname) <> ''", name="voteview_member_bioname_check"),
        sa.UniqueConstraint(
            "congress", "chamber", "icpsr", name="voteview_member_identity_key"
        ),
        schema="core",
    )
    op.create_index(
        "voteview_member_person_idx", "voteview_member", ["person_id"], schema="core"
    )


def _create_roll_call() -> None:
    op.create_table(
        "voteview_roll_call",
        sa.Column(
            "voteview_roll_call_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("congress", sa.Integer(), nullable=False),
        sa.Column("chamber", sa.Text(), nullable=False),
        sa.Column("rollnumber", sa.Integer(), nullable=False),
        sa.Column("session", sa.Integer()),
        sa.Column("clerk_rollnumber", sa.Integer()),
        sa.Column("vote_date", sa.Date()),
        sa.Column("majority_requirement", sa.Text()),
        sa.Column("yea_count", sa.Integer()),
        sa.Column("nay_count", sa.Integer()),
        sa.Column("nominate_mid_1", sa.Float()),
        sa.Column("nominate_mid_2", sa.Float()),
        sa.Column("nominate_spread_1", sa.Float()),
        sa.Column("nominate_spread_2", sa.Float()),
        sa.Column("nominate_log_likelihood", sa.Float()),
        sa.Column("bill_number", sa.Text()),
        sa.Column("vote_result", sa.Text()),
        sa.Column("vote_desc", sa.Text()),
        sa.Column("vote_question", sa.Text()),
        sa.Column("dtl_desc", sa.Text()),
        sa.Column("issue_codes", postgresql.JSONB()),
        sa.Column("peltzman_codes", postgresql.JSONB()),
        sa.Column("clausen_codes", postgresql.JSONB()),
        sa.Column("crs_policy_area", sa.Text()),
        sa.Column("crs_subjects", postgresql.JSONB()),
        sa.Column("congress_url", sa.Text()),
        sa.Column("source_documents", postgresql.JSONB()),
        sa.Column("roll_call_id", _UUID, sa.ForeignKey("core.roll_call.roll_call_id")),
        sa.Column("record", postgresql.JSONB(), nullable=False),
        *_evidence(),
        sa.CheckConstraint("congress > 0", name="voteview_roll_call_congress_check"),
        sa.CheckConstraint("rollnumber > 0", name="voteview_roll_call_number_check"),
        sa.CheckConstraint(
            "chamber IN ('house', 'senate')",
            name="voteview_roll_call_chamber_check",
        ),
        sa.UniqueConstraint(
            "congress", "chamber", "rollnumber", name="voteview_roll_call_identity_key"
        ),
        schema="core",
    )
    op.create_index(
        "voteview_roll_call_link_idx",
        "voteview_roll_call",
        ["roll_call_id"],
        schema="core",
    )


def _create_party() -> None:
    op.create_table(
        "voteview_party",
        sa.Column(
            "voteview_party_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("congress", sa.Integer(), nullable=False),
        sa.Column("chamber", sa.Text(), nullable=False),
        sa.Column("party_code", sa.Integer(), nullable=False),
        sa.Column("party_name", sa.Text(), nullable=False),
        sa.Column("n_members", sa.Integer()),
        sa.Column("nominate_dim1_median", sa.Float()),
        sa.Column("nominate_dim2_median", sa.Float()),
        sa.Column("nominate_dim1_mean", sa.Float()),
        sa.Column("nominate_dim2_mean", sa.Float()),
        sa.Column("record", postgresql.JSONB(), nullable=False),
        *_evidence(),
        sa.CheckConstraint("congress > 0", name="voteview_party_congress_check"),
        sa.CheckConstraint(
            "chamber IN ('house', 'senate', 'president')",
            name="voteview_party_chamber_check",
        ),
        sa.CheckConstraint("btrim(party_name) <> ''", name="voteview_party_name_check"),
        sa.UniqueConstraint(
            "congress", "chamber", "party_code", name="voteview_party_identity_key"
        ),
        schema="core",
    )


def _constraint_allows(name: str, token: str) -> bool:
    """True when a check already names ``token``.

    An adoption replay runs this revision again after a later one has widened
    the same check. Replacing it with this revision's text would reject those rows.
    """
    definition = op.get_bind().execute(
        sa.text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"),
        {"name": name},
    ).scalar()
    return bool(definition and token in definition)


def _widen_name_kinds() -> None:
    if _constraint_allows("person_name_source_kind_check", "middle"):
        return
    op.drop_constraint(
        "person_name_source_kind_check",
        "person_name_source",
        schema="core",
        type_="check",
    )
    op.create_check_constraint(
        "person_name_source_kind_check",
        "person_name_source",
        _PERSON_KIND,
        schema="core",
    )
    op.drop_constraint(
        "attribute_precedence_scope_check",
        "attribute_precedence",
        schema="catalog",
        type_="check",
    )
    op.create_check_constraint(
        "attribute_precedence_scope_check",
        "attribute_precedence",
        _PRECEDENCE_SCOPE,
        schema="catalog",
    )


def downgrade() -> None:
    """Remove the Voteview tables only when they are empty, then restore the name-kind checks."""
    bind = op.get_bind()
    for table in ("voteview_member", "voteview_roll_call", "voteview_party"):
        count = bind.execute(sa.text(f"SELECT count(*) FROM core.{table}")).scalar_one()
        if count:
            raise RuntimeError(
                f"core.{table} holds {count} rows; delete them (and re-sync later) before downgrading"
            )
    notes = bind.execute(
        sa.text("SELECT count(*) FROM core.person_name_source WHERE name_kind = 'voteview'")
    ).scalar_one()
    if notes:
        raise RuntimeError(
            f"core.person_name_source holds {notes} voteview rows; delete them "
            "(and re-sync later) before downgrading"
        )
    bind.execute(
        sa.text(
            "DELETE FROM catalog.attribute_precedence "
            "WHERE entity = 'person' AND name_kind = 'voteview'"
        )
    )
    op.drop_index("voteview_member_person_idx", table_name="voteview_member", schema="core")
    op.drop_table("voteview_member", schema="core")
    op.drop_index("voteview_roll_call_link_idx", table_name="voteview_roll_call", schema="core")
    op.drop_table("voteview_roll_call", schema="core")
    op.drop_table("voteview_party", schema="core")
    op.drop_constraint(
        "person_name_source_kind_check",
        "person_name_source",
        schema="core",
        type_="check",
    )
    op.create_check_constraint(
        "person_name_source_kind_check",
        "person_name_source",
        _PERSON_KIND_PRIOR,
        schema="core",
    )
    op.drop_constraint(
        "attribute_precedence_scope_check",
        "attribute_precedence",
        schema="catalog",
        type_="check",
    )
    op.create_check_constraint(
        "attribute_precedence_scope_check",
        "attribute_precedence",
        _PRECEDENCE_SCOPE_PRIOR,
        schema="catalog",
    )
