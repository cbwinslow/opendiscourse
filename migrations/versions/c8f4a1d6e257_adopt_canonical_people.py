"""adopt canonical people

Revision ID: c8f4a1d6e257
Revises: a5d9e2c7f418
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "c8f4a1d6e257"
down_revision: Union[str, Sequence[str], None] = "a5d9e2c7f418"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded canonical people and stable identifiers."""


def downgrade() -> None:
    """Retain canonical people at the prior adoption marker."""
