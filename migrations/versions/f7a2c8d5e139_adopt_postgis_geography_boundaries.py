"""adopt PostGIS geography boundaries

Revision ID: f7a2c8d5e139
Revises: b3f1d8e6c492
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "f7a2c8d5e139"
down_revision: Union[str, Sequence[str], None] = "b3f1d8e6c492"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded PostGIS geography boundaries."""


def downgrade() -> None:
    """Retain PostGIS boundaries at the prior adoption marker."""
