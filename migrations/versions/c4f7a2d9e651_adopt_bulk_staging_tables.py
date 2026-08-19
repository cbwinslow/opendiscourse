"""adopt bulk staging tables

Revision ID: c4f7a2d9e651
Revises: b9e3a6d4f182
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "c4f7a2d9e651"
down_revision: Union[str, Sequence[str], None] = "b9e3a6d4f182"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded provider-specific staging tables."""


def downgrade() -> None:
    """Retain bulk staging tables at the prior adoption marker."""
