"""adopt legislative dimensions

Revision ID: d4e6a1b9c573
Revises: f7a2c8d5e139
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "d4e6a1b9c573"
down_revision: Union[str, Sequence[str], None] = "f7a2c8d5e139"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded jurisdictions and legislative sessions."""


def downgrade() -> None:
    """Retain legislative dimensions at the prior adoption marker."""
