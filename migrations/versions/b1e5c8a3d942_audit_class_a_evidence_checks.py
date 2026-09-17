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
    op.execute(
        """
        DO $$
        DECLARE
            boundary_violations integer;
            document_violations integer;
        BEGIN
            SELECT count(*) INTO boundary_violations
            FROM core.geography_boundary
            WHERE source_artifact_id IS NULL AND source_payload_id IS NULL;

            IF boundary_violations > 0 THEN
                RAISE EXCEPTION 'preflight check failed: % sourceless rows in core.geography_boundary must be remediated before enforcing geography_boundary_check', boundary_violations;
            END IF;

            SELECT count(*) INTO document_violations
            FROM core.document
            WHERE artifact_id IS NULL AND source_payload_id IS NULL;

            IF document_violations > 0 THEN
                RAISE EXCEPTION 'preflight check failed: % sourceless rows in core.document must be remediated before enforcing document_check', document_violations;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE core.geography_boundary
        ADD CONSTRAINT geography_boundary_check
        CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
        NOT VALID;
        ALTER TABLE core.geography_boundary
        VALIDATE CONSTRAINT geography_boundary_check;
        """
    )
    op.execute(
        """
        ALTER TABLE core.document
        ADD CONSTRAINT document_check
        CHECK (artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
        NOT VALID;
        ALTER TABLE core.document
        VALIDATE CONSTRAINT document_check;
        """
    )


def downgrade() -> None:
    """Remove evidence CHECK constraints from core.geography_boundary and core.document."""
    op.drop_constraint("document_check", "document", schema="core", type_="check")
    op.drop_constraint(
        "geography_boundary_check", "geography_boundary", schema="core", type_="check"
    )
