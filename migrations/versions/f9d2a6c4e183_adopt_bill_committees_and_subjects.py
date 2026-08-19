"""adopt bill committees and subjects

Revision ID: f9d2a6c4e183
Revises: b6c3e8a1d574
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "f9d2a6c4e183"
down_revision: Union[str, Sequence[str], None] = "b6c3e8a1d574"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded bill committees and subjects."""


def downgrade() -> None:
    """Retain bill committees and subjects at the prior adoption marker."""
