"""adopt bill sponsorships

Revision ID: b6c3e8a1d574
Revises: e1b5d7a9c364
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "b6c3e8a1d574"
down_revision: Union[str, Sequence[str], None] = "e1b5d7a9c364"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded canonical bill sponsorships."""


def downgrade() -> None:
    """Retain bill sponsorships at the prior adoption marker."""
