"""adopt ingestion plan cursor

Revision ID: e6c9d2f41a85
Revises: c2d7e4a9b631
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "e6c9d2f41a85"
down_revision: Union[str, Sequence[str], None] = "c2d7e4a9b631"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt the legacy-seeded shared ingestion plan cursor."""


def downgrade() -> None:
    """Retain the legacy plan cursor at the prior adoption marker."""
