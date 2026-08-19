"""adopt ingestion artifacts

Revision ID: c2d7e4a9b631
Revises: a9e4c1b78f20
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "c2d7e4a9b631"
down_revision: Union[str, Sequence[str], None] = "a9e4c1b78f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded immutable artifact evidence."""


def downgrade() -> None:
    """Retain legacy artifact evidence at the prior adoption marker."""
