"""Current committee membership: source records, committees, and assignments.

Revision ID: c4e8a1b93d27
Revises: b8c4e2a17f03

Expand only. Subcommittee identity is the membership-file key (parent thomas id
plus the short code). Short codes such as 01 repeat across parents, so they are
not unique on their own. ``roster`` is a person-name kind that is ranked and
never displayed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4e8a1b93d27"
down_revision: str | Sequence[str] | None = "b8c4e2a17f03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)

_PERSON_KIND = "name_kind IN ('official', 'common', 'roster')"
_PERSON_KIND_PRIOR = "name_kind IN ('official', 'common')"
_PRECEDENCE_SCOPE = (
    "(entity = 'person' AND name_kind IN ('official', 'common', 'roster') AND geography_type = '') "
    "OR (entity = 'geography' AND name_kind IN ('short', 'full') AND geography_type <> '')"
)
_PRECEDENCE_SCOPE_PRIOR = (
    "(entity = 'person' AND name_kind IN ('official', 'common') AND geography_type = '') "
    "OR (entity = 'geography' AND name_kind IN ('short', 'full') AND geography_type <> '')"
)


def upgrade() -> None:
    """Add the committee snapshot tables and allow the roster name kind.

    Guarded so a database that already has the tables (an adoption replay after
    the Alembic watermark was removed) does not try to create them again.
    """
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("committee_source_record", schema="core"):
        _create_source_record()
    if not inspector.has_table("committee", schema="core"):
        _create_committee()
    if not inspector.has_table("committee_assignment", schema="core"):
        _create_assignment()
    _widen_name_kinds()


def _create_source_record() -> None:
    op.create_table(
        "committee_source_record",
        sa.Column(
            "committee_source_record_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("thomas_key", sa.Text(), nullable=False),
        sa.Column("bioguide", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("record", postgresql.JSONB(), nullable=False),
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
        sa.CheckConstraint("btrim(source_file) <> ''", name="committee_source_record_file_check"),
        sa.CheckConstraint("btrim(thomas_key) <> ''", name="committee_source_record_key_check"),
        sa.UniqueConstraint(
            "source_file",
            "thomas_key",
            "bioguide",
            name="committee_source_record_identity_key",
        ),
        schema="core",
    )


def _create_committee() -> None:
    op.create_table(
        "committee",
        sa.Column(
            "committee_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("thomas_key", sa.Text(), nullable=False),
        sa.Column("parent_thomas_key", sa.Text()),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("chamber", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("minority_url", sa.Text()),
        sa.Column("house_committee_id", sa.Text()),
        sa.Column("senate_committee_id", sa.Text()),
        sa.Column("address", sa.Text()),
        sa.Column("phone", sa.Text()),
        sa.Column("rss_url", sa.Text()),
        sa.Column("minority_rss_url", sa.Text()),
        sa.Column("jurisdiction", sa.Text()),
        sa.Column("jurisdiction_source", sa.Text()),
        sa.Column("wikipedia", sa.Text()),
        sa.Column("youtube_id", sa.Text()),
        sa.Column(
            "congresses",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{}'::integer[]"),
        ),
        sa.Column(
            "former_names",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "source_artifact_id",
            _UUID,
            sa.ForeignKey("ingest.artifact.artifact_id"),
            nullable=False,
        ),
        sa.Column(
            "history_artifact_id",
            _UUID,
            sa.ForeignKey("ingest.artifact.artifact_id"),
        ),
        sa.Column("run_id", _UUID, sa.ForeignKey("ingest.run.run_id"), nullable=False),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("btrim(thomas_key) <> ''", name="committee_thomas_key_check"),
        sa.CheckConstraint("btrim(name) <> ''", name="committee_name_check"),
        sa.CheckConstraint(
            "chamber IN ('house', 'senate', 'joint')",
            name="committee_chamber_check",
        ),
        sa.CheckConstraint(
            "(kind = 'committee' AND parent_thomas_key IS NULL) "
            "OR (kind = 'subcommittee' AND parent_thomas_key IS NOT NULL "
            "AND btrim(parent_thomas_key) <> '')",
            name="committee_kind_parent_check",
        ),
        sa.UniqueConstraint("thomas_key", name="committee_thomas_key_key"),
        schema="core",
    )
    op.create_index("committee_parent_idx", "committee", ["parent_thomas_key"], schema="core")


def _create_assignment() -> None:
    op.create_table(
        "committee_assignment",
        sa.Column(
            "committee_assignment_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "committee_id",
            _UUID,
            sa.ForeignKey("core.committee.committee_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("person_id", _UUID, sa.ForeignKey("core.person.person_id")),
        sa.Column("bioguide", sa.Text(), nullable=False),
        sa.Column("party", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("stated_name", sa.Text(), nullable=False),
        sa.Column("chamber", sa.Text()),
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
        sa.CheckConstraint("btrim(bioguide) <> ''", name="committee_assignment_bioguide_check"),
        sa.CheckConstraint("btrim(stated_name) <> ''", name="committee_assignment_name_check"),
        sa.CheckConstraint(
            "party IN ('majority', 'minority')",
            name="committee_assignment_party_check",
        ),
        sa.CheckConstraint(
            "chamber IS NULL OR chamber IN ('house', 'senate')",
            name="committee_assignment_chamber_check",
        ),
        sa.UniqueConstraint(
            "committee_id",
            "bioguide",
            name="committee_assignment_committee_bioguide_key",
        ),
        schema="core",
    )
    op.create_index(
        "committee_assignment_person_idx",
        "committee_assignment",
        ["person_id"],
        schema="core",
    )


def _constraint_allows(name: str, token: str) -> bool:
    """True when a check already names ``token``.

    An adoption replay runs this revision again after a later one has widened
    the same check. Replacing it with the older text would reject those rows.
    """
    definition = op.get_bind().execute(
        sa.text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"),
        {"name": name},
    ).scalar()
    return bool(definition and token in definition)


def _widen_name_kinds() -> None:
    if _constraint_allows("person_name_source_kind_check", "voteview"):
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
    """Remove the snapshot tables only when they are empty, then restore the name-kind checks."""
    bind = op.get_bind()
    for table in ("committee_assignment", "committee_source_record", "committee"):
        count = bind.execute(sa.text(f"SELECT count(*) FROM core.{table}")).scalar_one()
        if count:
            raise RuntimeError(
                f"core.{table} holds {count} rows; delete them (and re-sync later) before downgrading"
            )
    roster_names = bind.execute(
        sa.text("SELECT count(*) FROM core.person_name_source WHERE name_kind = 'roster'")
    ).scalar_one()
    if roster_names:
        raise RuntimeError(
            f"core.person_name_source holds {roster_names} roster rows; delete them "
            "(and re-sync later) before downgrading"
        )
    # Ranks are configuration copied from inventory/precedence.yaml. The narrower
    # check cannot be restored while they exist, and a later upgrade syncs them again.
    bind.execute(
        sa.text(
            "DELETE FROM catalog.attribute_precedence "
            "WHERE entity = 'person' AND name_kind = 'roster'"
        )
    )
    op.drop_index("committee_assignment_person_idx", table_name="committee_assignment", schema="core")
    op.drop_table("committee_assignment", schema="core")
    op.drop_index("committee_parent_idx", table_name="committee", schema="core")
    op.drop_table("committee", schema="core")
    op.drop_table("committee_source_record", schema="core")
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
