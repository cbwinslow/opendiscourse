"""Preserve every checksum-bearing artifact revision as evidence.

Revision ID: d9e4f1a7b632
Revises: b1e5c8a3d942
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e4f1a7b632"
down_revision: str | Sequence[str] | None = "b1e5c8a3d942"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the append-only version discriminator without changing existing rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("artifact", schema="ingest")}
    constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("artifact", schema="ingest")
    }
    if "artifact_version" not in columns:
        op.add_column(
            "artifact",
            sa.Column("artifact_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            schema="ingest",
        )
    if "artifact_dataset_id_artifact_key_key" in constraints:
        op.drop_constraint("artifact_dataset_id_artifact_key_key", "artifact", schema="ingest", type_="unique")
    if "artifact_dataset_id_artifact_key_version_key" not in constraints:
        op.create_unique_constraint(
            "artifact_dataset_id_artifact_key_version_key",
            "artifact",
            ["dataset_id", "artifact_key", "artifact_version"],
            schema="ingest",
        )
    # One definition of "the version consumers should read": the newest version
    # whose bytes are usable. A later failed refresh must not hide verified bytes.
    op.execute(
        """
        CREATE OR REPLACE VIEW ingest.current_artifact AS
        SELECT DISTINCT ON (dataset_id, artifact_key) *
        FROM ingest.artifact
        WHERE status IN ('downloaded', 'skipped', 'loaded')
        ORDER BY dataset_id, artifact_key, artifact_version DESC
        """
    )


def downgrade() -> None:
    """Refuse a downgrade that would merge or discard retained evidence."""
    op.execute(
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM ingest.artifact
            GROUP BY dataset_id, artifact_key HAVING count(*) > 1
          ) THEN
            RAISE EXCEPTION
              'cannot downgrade immutable artifact versions: artifact history exists; no evidence was changed';
          END IF;
        END $$;
        """
    )
    op.execute("DROP VIEW IF EXISTS ingest.current_artifact")
    op.drop_constraint("artifact_dataset_id_artifact_key_version_key", "artifact", schema="ingest", type_="unique")
    op.create_unique_constraint("artifact_dataset_id_artifact_key_key", "artifact", ["dataset_id", "artifact_key"], schema="ingest")
    op.drop_column("artifact", "artifact_version", schema="ingest")
