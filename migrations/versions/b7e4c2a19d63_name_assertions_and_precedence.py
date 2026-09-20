"""Name assertions, precedence tables and the resolver write guard (Story 10.2, ADR-0005).

Revision ID: b7e4c2a19d63
Revises: a4d9e1c7b356
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e4c2a19d63"
down_revision: str | Sequence[str] | None = "a4d9e1c7b356"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)

# Vintages are ordered as text by the resolver, so only zero-padded ISO forms are allowed.
VINTAGE_CHECK = "source_vintage ~ '^[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?$'"

# The resolver says it is the writer with `SET LOCAL opendiscourse.resolver = 'on'`. This stops accidental
# writes, not a determined one: any session can set that flag. To delete assertions a resolved row points
# at, the wipe transaction sets the flag and nulls the pointer first.
_GUARD_PERSON = """
CREATE OR REPLACE FUNCTION core.guard_person_names() RETURNS trigger LANGUAGE plpgsql AS $guard$
BEGIN
  IF coalesce(current_setting('opendiscourse.resolver', true), '') = 'on' THEN
    RETURN NEW;
  END IF;
  IF NEW.name_source_id IS DISTINCT FROM OLD.name_source_id
     OR (OLD.name_source_id IS NOT NULL
         AND (NEW.full_name, NEW.given_name, NEW.family_name)
             IS DISTINCT FROM (OLD.full_name, OLD.given_name, OLD.family_name)) THEN
    RAISE EXCEPTION 'core.person names of person % are written only by "research-db resolve"', OLD.person_id
      USING ERRCODE = '42501', HINT = 'Record what a source says in core.person_name_source; the resolver shows it.';
  END IF;
  RETURN NEW;
END
$guard$
"""

_GUARD_GEOGRAPHY = """
CREATE OR REPLACE FUNCTION core.guard_geography_name() RETURNS trigger LANGUAGE plpgsql AS $guard$
BEGIN
  IF coalesce(current_setting('opendiscourse.resolver', true), '') = 'on' THEN
    RETURN NEW;
  END IF;
  IF NEW.name_source_id IS DISTINCT FROM OLD.name_source_id
     OR (OLD.name_source_id IS NOT NULL AND NEW.name IS DISTINCT FROM OLD.name) THEN
    RAISE EXCEPTION 'core.geography name of %/% is written only by "research-db resolve"',
      OLD.geography_type, OLD.geoid
      USING ERRCODE = '42501', HINT = 'Record what a source says in core.geography_name_source; the resolver shows it.';
  END IF;
  RETURN NEW;
END
$guard$
"""


def _evidence_columns() -> list[sa.Column]:
    return [
        sa.Column("dataset_id", sa.Text(), sa.ForeignKey("catalog.dataset.dataset_id"), nullable=False),
        # Zero-padded ISO text (2024, 2024-09), enforced by a check: ordered COLLATE "C" by the resolver.
        sa.Column("source_vintage", sa.Text(), nullable=False),
        # ADR-0002 rule 3: artifact OR payload, plus run.
        sa.Column("artifact_id", _UUID, sa.ForeignKey("ingest.artifact.artifact_id")),
        sa.Column("payload_id", _UUID, sa.ForeignKey("ingest.raw_payload.payload_id")),
        sa.Column("run_id", _UUID, sa.ForeignKey("ingest.run.run_id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    """Expand only: new tables, two nullable pointer columns, two guard triggers."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("attribute_precedence", schema="catalog"):
        op.create_table(
            "attribute_precedence",
            sa.Column("entity", sa.Text(), nullable=False),
            sa.Column("name_kind", sa.Text(), nullable=False),
            # '' for person, which has no types; the geography type otherwise.
            sa.Column("geography_type", sa.Text(), nullable=False, server_default=sa.text("''")),
            sa.Column("rank", sa.SmallInteger(), nullable=False),
            sa.Column("dataset_id", sa.Text(), sa.ForeignKey("catalog.dataset.dataset_id"), nullable=False),
            # Documents the source field; the resolver does not read it.
            sa.Column("field", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("entity", "name_kind", "geography_type", "dataset_id"),
            sa.UniqueConstraint(
                "entity", "name_kind", "geography_type", "rank",
                name="attribute_precedence_rank_key", deferrable=True, initially="DEFERRED",
            ),
            sa.CheckConstraint("rank > 0", name="attribute_precedence_rank_check"),
            sa.CheckConstraint(
                "(entity = 'person' AND name_kind IN ('official', 'common') AND geography_type = '') "
                "OR (entity = 'geography' AND name_kind IN ('short', 'full') AND geography_type <> '')",
                name="attribute_precedence_scope_check",
            ),
            schema="catalog",
        )
    if not inspector.has_table("name_display", schema="catalog"):
        op.create_table(
            "name_display",
            sa.Column("entity", sa.Text(), nullable=False),
            sa.Column("name_kind", sa.Text(), nullable=False),
            # 1 is shown when it has any assertion; later kinds are the fallback.
            sa.Column("position", sa.SmallInteger(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("entity", "name_kind"),
            sa.UniqueConstraint(
                "entity", "position", name="name_display_position_key", deferrable=True, initially="DEFERRED"
            ),
            sa.CheckConstraint("position > 0", name="name_display_position_check"),
            sa.CheckConstraint(
                "(entity = 'person' AND name_kind IN ('official', 'common')) "
                "OR (entity = 'geography' AND name_kind IN ('short', 'full'))",
                name="name_display_kind_check",
            ),
            schema="catalog",
        )
    if not inspector.has_table("person_name_source", schema="core"):
        op.create_table(
            "person_name_source",
            sa.Column("person_name_source_id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("person_id", _UUID, sa.ForeignKey("core.person.person_id", ondelete="CASCADE"), nullable=False),
            sa.Column("name_kind", sa.Text(), nullable=False),
            # The full/given/family triple travels together, exactly as the source gave it.
            sa.Column("full_name", sa.Text(), nullable=False),
            sa.Column("given_name", sa.Text()),
            sa.Column("family_name", sa.Text()),
            *_evidence_columns(),
            sa.CheckConstraint("name_kind IN ('official', 'common')", name="person_name_source_kind_check"),
            sa.CheckConstraint("btrim(full_name) <> ''", name="person_name_source_name_check"),
            sa.CheckConstraint(
                "artifact_id IS NOT NULL OR payload_id IS NOT NULL", name="person_name_source_evidence"
            ),
            sa.CheckConstraint(VINTAGE_CHECK, name="person_name_source_vintage_check"),
            sa.UniqueConstraint(
                "person_id", "name_kind", "dataset_id", "source_vintage",
                name="person_name_source_key", postgresql_nulls_not_distinct=True,
            ),
            schema="core",
        )
        op.create_index("person_name_source_dataset_idx", "person_name_source", ["dataset_id"], schema="core")
    if not inspector.has_table("geography_name_source", schema="core"):
        op.create_table(
            "geography_name_source",
            sa.Column("geography_name_source_id", _UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "geography_id", _UUID, sa.ForeignKey("core.geography.geography_id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("name_kind", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            *_evidence_columns(),
            sa.CheckConstraint("name_kind IN ('short', 'full')", name="geography_name_source_kind_check"),
            sa.CheckConstraint("btrim(name) <> ''", name="geography_name_source_name_check"),
            sa.CheckConstraint(
                "artifact_id IS NOT NULL OR payload_id IS NOT NULL", name="geography_name_source_evidence"
            ),
            sa.CheckConstraint(VINTAGE_CHECK, name="geography_name_source_vintage_check"),
            sa.UniqueConstraint(
                "geography_id", "name_kind", "dataset_id", "source_vintage",
                name="geography_name_source_key", postgresql_nulls_not_distinct=True,
            ),
            schema="core",
        )
        op.create_index("geography_name_source_dataset_idx", "geography_name_source", ["dataset_id"], schema="core")
    for table, source in (("person", "person_name_source"), ("geography", "geography_name_source")):
        columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table, schema="core")}
        if "name_source_id" not in columns:
            op.add_column(table, sa.Column("name_source_id", _UUID), schema="core")
            op.create_foreign_key(
                f"{table}_name_source_fk", table, source, ["name_source_id"], [f"{source}_id"],
                source_schema="core", referent_schema="core",
            )
    # Partial: only resolved rows point, and deleting an assertion must find its pointing row quickly.
    op.execute(
        "CREATE INDEX IF NOT EXISTS person_name_source_pointer_idx ON core.person (name_source_id) "
        "WHERE name_source_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS geography_name_source_pointer_idx ON core.geography (name_source_id) "
        "WHERE name_source_id IS NOT NULL"
    )
    op.execute(_GUARD_PERSON)
    op.execute(_GUARD_GEOGRAPHY)
    # Replayable: an existing schema without the alembic watermark is adopted, not rebuilt.
    op.execute("DROP TRIGGER IF EXISTS person_names_guard ON core.person")
    op.execute("DROP TRIGGER IF EXISTS geography_name_guard ON core.geography")
    op.execute(
        "CREATE TRIGGER person_names_guard BEFORE UPDATE OF full_name, given_name, family_name, name_source_id "
        "ON core.person FOR EACH ROW EXECUTE FUNCTION core.guard_person_names()"
    )
    op.execute(
        "CREATE TRIGGER geography_name_guard BEFORE UPDATE OF name, name_source_id "
        "ON core.geography FOR EACH ROW EXECUTE FUNCTION core.guard_geography_name()"
    )


def downgrade() -> None:
    """Refuse when assertions exist: they are the only copy of the losing values and their evidence."""
    bind = op.get_bind()
    for table in ("person_name_source", "geography_name_source"):
        if sa.inspect(bind).has_table(table, schema="core"):
            count = bind.execute(sa.text(f"SELECT count(*) FROM core.{table}")).scalar_one()
            if count:
                raise RuntimeError(f"core.{table} holds {count} rows; export them before downgrading")
    op.execute("DROP TRIGGER IF EXISTS person_names_guard ON core.person")
    op.execute("DROP TRIGGER IF EXISTS geography_name_guard ON core.geography")
    op.execute("DROP FUNCTION IF EXISTS core.guard_person_names()")
    op.execute("DROP FUNCTION IF EXISTS core.guard_geography_name()")
    op.execute("DROP INDEX IF EXISTS core.person_name_source_pointer_idx")
    op.execute("DROP INDEX IF EXISTS core.geography_name_source_pointer_idx")
    op.execute("ALTER TABLE core.person DROP COLUMN IF EXISTS name_source_id")
    op.execute("ALTER TABLE core.geography DROP COLUMN IF EXISTS name_source_id")
    op.drop_table("person_name_source", schema="core", if_exists=True)
    op.drop_table("geography_name_source", schema="core", if_exists=True)
    op.drop_table("name_display", schema="catalog", if_exists=True)
    op.drop_table("attribute_precedence", schema="catalog", if_exists=True)
