"""adopt canonical organizations

Revision ID: a2e6c4d9f187
Revises: d7a4e1c9b265
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "a2e6c4d9f187"
down_revision: Union[str, Sequence[str], None] = "d7a4e1c9b265"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded organizations and stable identifiers."""


def downgrade() -> None:
    """Retain canonical organizations at the prior adoption marker."""
