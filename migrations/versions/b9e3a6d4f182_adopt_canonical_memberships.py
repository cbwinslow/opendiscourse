"""adopt canonical memberships

Revision ID: b9e3a6d4f182
Revises: a8d5e2c7f361
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "b9e3a6d4f182"
down_revision: Union[str, Sequence[str], None] = "a8d5e2c7f361"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt the legacy-seeded canonical membership table."""


def downgrade() -> None:
    """Retain memberships at the prior adoption marker."""
