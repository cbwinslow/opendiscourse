"""adopt ingestion run evidence

Revision ID: a9e4c1b78f20
Revises: f5e8a3c47d12
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "a9e4c1b78f20"
down_revision: Union[str, Sequence[str], None] = "f5e8a3c47d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded ingestion run and raw-payload tables."""


def downgrade() -> None:
    """Retain legacy ingestion evidence tables at the prior adoption marker."""
