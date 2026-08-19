"""adopt canonical bill identity

Revision ID: a5d9e2c7f418
Revises: d4e6a1b9c573
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "a5d9e2c7f418"
down_revision: Union[str, Sequence[str], None] = "d4e6a1b9c573"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded canonical bill identity and provenance."""


def downgrade() -> None:
    """Retain canonical bill identity at the prior adoption marker."""
