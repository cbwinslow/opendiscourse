"""adopt business patterns

Revision ID: c5a7e2d8b419
Revises: b4e8c1d7a593
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "c5a7e2d8b419"
down_revision: Union[str, Sequence[str], None] = "b4e8c1d7a593"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded CBP business-pattern facts."""


def downgrade() -> None:
    """Retain business patterns at the prior adoption marker."""
