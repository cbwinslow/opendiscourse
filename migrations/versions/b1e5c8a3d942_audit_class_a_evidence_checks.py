"""audit class a evidence checks

Revision ID: b1e5c8a3d942
Revises: a4f8c2e9b176
Create Date: 2026-09-17
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b1e5c8a3d942"
down_revision: Union[str, Sequence[str], None] = "a4f8c2e9b176"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enforce evidence CHECK constraints on core.geography_boundary and core.document."""
    op.create_check_constraint(
        "geography_boundary_check",
        "geography_boundary",
        "source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        schema="core",
    )
    op.create_check_constraint(
        "document_check",
        "document",
        "artifact_id IS NOT NULL OR source_payload_id IS NOT NULL",
        schema="core",
    )


def downgrade() -> None:
    """Remove evidence CHECK constraints from core.geography_boundary and core.document."""
    op.drop_constraint("document_check", "document", schema="core", type_="check")
    op.drop_constraint(
        "geography_boundary_check", "geography_boundary", schema="core", type_="check"
    )
