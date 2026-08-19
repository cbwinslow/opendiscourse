"""adopt ingest evidence tables

Revision ID: f5e8a3c47d12
Revises: d207df35ca10
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "f5e8a3c47d12"
down_revision: Union[str, Sequence[str], None] = "d207df35ca10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded OpenStates evidence tables for future Alembic changes."""


def downgrade() -> None:
    """Keep legacy evidence tables intact when returning to the catalog baseline."""
