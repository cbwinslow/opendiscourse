"""adopt financial primitives

Revision ID: f1c7e3a9d582
Revises: e4c2a9d6b731
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "f1c7e3a9d582"
down_revision: Union[str, Sequence[str], None] = "e4c2a9d6b731"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded instruments, symbols, and market bars."""


def downgrade() -> None:
    """Retain financial primitives at the prior adoption marker."""
