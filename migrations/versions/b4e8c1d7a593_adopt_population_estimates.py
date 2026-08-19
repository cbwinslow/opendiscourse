"""adopt population estimates

Revision ID: b4e8c1d7a593
Revises: e8b1c5d4a296
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "b4e8c1d7a593"
down_revision: Union[str, Sequence[str], None] = "e8b1c5d4a296"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded PEP population estimates."""


def downgrade() -> None:
    """Retain population estimates at the prior adoption marker."""
