"""immutable artifact versions

Revision ID: c5e2d1a4f783
Revises: b1e5c8a3d942
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5e2d1a4f783"
down_revision: Union[str, Sequence[str], None] = "b1e5c8a3d942"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add artifact_version to ingest.artifact and enforce uniqueness on (dataset_id, artifact_key, artifact_version)."""
    op.add_column(
        "artifact",
        sa.Column(
            "artifact_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        schema="ingest",
    )
    op.drop_constraint(
        "artifact_dataset_id_artifact_key_key",
        "artifact",
        schema="ingest",
        type_="unique",
    )
    op.create_unique_constraint(
        "artifact_dataset_id_artifact_key_version_key",
        "artifact",
        ["dataset_id", "artifact_key", "artifact_version"],
        schema="ingest",
    )


def downgrade() -> None:
    """Revert uniqueness to (dataset_id, artifact_key) and remove artifact_version column."""
    op.drop_constraint(
        "artifact_dataset_id_artifact_key_version_key",
        "artifact",
        schema="ingest",
        type_="unique",
    )
    op.execute(
        """
        DELETE FROM ingest.artifact
        WHERE (dataset_id, artifact_key, artifact_version) NOT IN (
            SELECT dataset_id, artifact_key, MAX(artifact_version)
            FROM ingest.artifact
            GROUP BY dataset_id, artifact_key
        )
        """
    )
    op.create_unique_constraint(
        "artifact_dataset_id_artifact_key_key",
        "artifact",
        ["dataset_id", "artifact_key"],
        schema="ingest",
    )
    op.drop_column("artifact", "artifact_version", schema="ingest")
