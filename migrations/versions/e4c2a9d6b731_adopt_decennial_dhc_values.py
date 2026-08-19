"""adopt decennial DHC values

Revision ID: e4c2a9d6b731
Revises: d3f6a8c1e274
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "e4c2a9d6b731"
down_revision: Union[str, Sequence[str], None] = "d3f6a8c1e274"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded decennial DHC facts."""


def downgrade() -> None:
    """Retain DHC values at the prior adoption marker."""
