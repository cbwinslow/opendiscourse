"""Member profile: biography, leadership, contact, social accounts, district offices.

Revision ID: c9e4a1b27d83
Revises: e8c2a9d14b59

Expand only. Middle, suffix, nickname, and former are name kinds that are ranked
and never displayed. The shown name stays the common name.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "c9e4a1b27d83"
down_revision: str | Sequence[str] | None = "e8c2a9d14b59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)
_PERSON_KIND = (
    "name_kind IN ('official', 'common', 'roster', 'voteview', "
    "'middle', 'suffix', 'nickname', 'former')"
)
_PERSON_KIND_PRIOR = "name_kind IN ('official', 'common', 'roster', 'voteview')"
_PRECEDENCE_SCOPE = (
    "(entity = 'person' AND name_kind IN ('official', 'common', 'roster', 'voteview', "
    "'middle', 'suffix', 'nickname', 'former') AND geography_type = '') "
    "OR (entity = 'geography' AND name_kind IN ('short', 'full') AND geography_type <> '')"
)
_PRECEDENCE_SCOPE_PRIOR = (
    "(entity = 'person' AND name_kind IN ('official', 'common', 'roster', 'voteview') "
    "AND geography_type = '') "
    "OR (entity = 'geography' AND name_kind IN ('short', 'full') AND geography_type <> '')"
)
_CONTACT = ("office", "address", "phone", "fax", "contact_form", "url", "rss_url")


def upgrade() -> None:
    """Add the member-profile tables and allow the extra name kinds."""
    inspector = sa.inspect(op.get_bind())
    _add_person_columns(inspector)
    _add_contact_columns(inspector)
    if not inspector.has_table("legislator_source_record", schema="core"):
        _create_source_record()
    if not inspector.has_table("person_leadership", schema="core"):
        _create_leadership()
    if not inspector.has_table("person_social_account", schema="core"):
        _create_social()
    if not inspector.has_table("district_office", schema="core"):
        _create_office()
    _widen_name_kinds()


def _add_person_columns(inspector: sa.Inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns("person", schema="core")}
    if "birthday" not in columns:
        op.add_column("person", sa.Column("birthday", sa.Date()), schema="core")
    if "gender" not in columns:
        op.add_column("person", sa.Column("gender", sa.Text()), schema="core")
        op.create_check_constraint(
            "person_gender_check",
            "person",
            "gender IS NULL OR btrim(gender) <> ''",
            schema="core",
        )


def _add_contact_columns(inspector: sa.Inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns("membership", schema="core")}
    for name in _CONTACT:
        if name not in columns:
            op.add_column("membership", sa.Column(name, sa.Text()), schema="core")


def _create_source_record() -> None:
    op.create_table(
        "legislator_source_record",
        sa.Column(
            "legislator_source_record_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("member_key", sa.Text(), nullable=False),
        sa.Column("bioguide", sa.Text(), nullable=False),
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
        sa.CheckConstraint("btrim(source_file) <> ''", name="legislator_source_record_file_check"),
        sa.CheckConstraint("btrim(member_key) <> ''", name="legislator_source_record_key_check"),
        sa.CheckConstraint("btrim(bioguide) <> ''", name="legislator_source_record_bioguide_check"),
        sa.UniqueConstraint(
            "source_file",
            "member_key",
            "bioguide",
            name="legislator_source_record_identity_key",
        ),
        schema="core",
    )


def _create_leadership() -> None:
    op.create_table(
        "person_leadership",
        sa.Column(
            "person_leadership_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("person_id", _UUID, sa.ForeignKey("core.person.person_id", ondelete="CASCADE")),
        sa.Column("bioguide", sa.Text(), nullable=False),
        sa.Column("chamber", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
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
        sa.CheckConstraint("btrim(bioguide) <> ''", name="person_leadership_bioguide_check"),
        sa.CheckConstraint("btrim(title) <> ''", name="person_leadership_title_check"),
        sa.CheckConstraint(
            "chamber IN ('house', 'senate')",
            name="person_leadership_chamber_check",
        ),
        sa.UniqueConstraint(
            "bioguide",
            "chamber",
            "title",
            "start_date",
            name="person_leadership_identity_key",
        ),
        schema="core",
    )
    op.create_index(
        "person_leadership_person_idx",
        "person_leadership",
        ["person_id"],
        schema="core",
    )


def _create_social() -> None:
    op.create_table(
        "person_social_account",
        sa.Column(
            "person_social_account_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("person_id", _UUID, sa.ForeignKey("core.person.person_id", ondelete="CASCADE")),
        sa.Column("bioguide", sa.Text(), nullable=False),
        sa.Column("network", sa.Text(), nullable=False),
        sa.Column("handle", sa.Text()),
        sa.Column("external_id", sa.Text()),
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
        sa.CheckConstraint("btrim(bioguide) <> ''", name="person_social_account_bioguide_check"),
        sa.CheckConstraint(
            "network IN ('twitter', 'facebook', 'instagram', 'youtube', 'mastodon')",
            name="person_social_account_network_check",
        ),
        sa.CheckConstraint(
            "handle IS NOT NULL OR external_id IS NOT NULL",
            name="person_social_account_value_check",
        ),
        sa.UniqueConstraint("bioguide", "network", name="person_social_account_identity_key"),
        schema="core",
    )
    op.create_index(
        "person_social_account_person_idx",
        "person_social_account",
        ["person_id"],
        schema="core",
    )


def _create_office() -> None:
    op.create_table(
        "district_office",
        sa.Column(
            "district_office_id",
            _UUID,
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("person_id", _UUID, sa.ForeignKey("core.person.person_id", ondelete="CASCADE")),
        sa.Column("bioguide", sa.Text(), nullable=False),
        sa.Column("office_key", sa.Text(), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("building", sa.Text()),
        sa.Column("suite", sa.Text()),
        sa.Column("city", sa.Text()),
        sa.Column("state", sa.Text()),
        sa.Column("zip", sa.Text()),
        sa.Column("phone", sa.Text()),
        sa.Column("fax", sa.Text()),
        sa.Column("hours", sa.Text()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column(
            "location",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        ),
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
        sa.CheckConstraint("btrim(bioguide) <> ''", name="district_office_bioguide_check"),
        sa.CheckConstraint("btrim(office_key) <> ''", name="district_office_key_check"),
        sa.CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="district_office_coordinates_check",
        ),
        sa.UniqueConstraint("office_key", name="district_office_key_key"),
        schema="core",
    )
    op.create_index("district_office_person_idx", "district_office", ["person_id"], schema="core")


def _widen_name_kinds() -> None:
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
    """Remove the profile tables only when they are empty, then restore the name-kind checks."""
    bind = op.get_bind()
    for table in (
        "person_leadership",
        "person_social_account",
        "district_office",
        "legislator_source_record",
    ):
        count = bind.execute(sa.text(f"SELECT count(*) FROM core.{table}")).scalar_one()
        if count:
            raise RuntimeError(
                f"core.{table} holds {count} rows; delete them before downgrading"
            )
    notes = bind.execute(
        sa.text(
            "SELECT count(*) FROM core.person_name_source "
            "WHERE name_kind IN ('middle', 'suffix', 'nickname', 'former')"
        )
    ).scalar_one()
    if notes:
        raise RuntimeError(
            f"core.person_name_source holds {notes} profile name rows; delete them before downgrading"
        )
    filled = bind.execute(
        sa.text(
            "SELECT count(*) FROM core.person WHERE birthday IS NOT NULL OR gender IS NOT NULL"
        )
    ).scalar_one()
    if filled:
        raise RuntimeError(
            f"core.person holds {filled} biography values; clear them before downgrading"
        )
    contact = " OR ".join(f"{name} IS NOT NULL" for name in _CONTACT)
    filled_contact = bind.execute(
        sa.text(f"SELECT count(*) FROM core.membership WHERE {contact}")
    ).scalar_one()
    if filled_contact:
        raise RuntimeError(
            f"core.membership holds {filled_contact} Washington contact values; "
            "clear them before downgrading"
        )
    bind.execute(
        sa.text(
            "DELETE FROM catalog.attribute_precedence "
            "WHERE entity = 'person' AND name_kind IN ('middle', 'suffix', 'nickname', 'former')"
        )
    )
    op.drop_index("district_office_person_idx", table_name="district_office", schema="core")
    op.drop_table("district_office", schema="core")
    op.drop_index("person_social_account_person_idx", table_name="person_social_account", schema="core")
    op.drop_table("person_social_account", schema="core")
    op.drop_index("person_leadership_person_idx", table_name="person_leadership", schema="core")
    op.drop_table("person_leadership", schema="core")
    op.drop_table("legislator_source_record", schema="core")
    for name in reversed(_CONTACT):
        op.drop_column("membership", name, schema="core")
    op.drop_constraint("person_gender_check", "person", schema="core", type_="check")
    op.drop_column("person", "gender", schema="core")
    op.drop_column("person", "birthday", schema="core")
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
