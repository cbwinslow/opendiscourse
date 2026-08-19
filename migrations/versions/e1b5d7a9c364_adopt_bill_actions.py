"""adopt bill actions

Revision ID: e1b5d7a9c364
Revises: c8f4a1d6e257
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "e1b5d7a9c364"
down_revision: Union[str, Sequence[str], None] = "c8f4a1d6e257"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded canonical bill actions."""


def downgrade() -> None:
    """Retain bill actions at the prior adoption marker."""
