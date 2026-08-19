"""adopt ACS bulk estimates

Revision ID: d3f6a8c1e274
Revises: c5a7e2d8b419
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "d3f6a8c1e274"
down_revision: Union[str, Sequence[str], None] = "c5a7e2d8b419"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded ACS bulk-estimate facts."""


def downgrade() -> None:
    """Retain ACS bulk estimates at the prior adoption marker."""
