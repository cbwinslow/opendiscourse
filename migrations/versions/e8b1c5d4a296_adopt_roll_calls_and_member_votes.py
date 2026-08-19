"""adopt roll calls and member votes

Revision ID: e8b1c5d4a296
Revises: a2e6c4d9f187
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "e8b1c5d4a296"
down_revision: Union[str, Sequence[str], None] = "a2e6c4d9f187"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded roll calls and source-evidenced member votes."""


def downgrade() -> None:
    """Retain voting facts at the prior adoption marker."""
