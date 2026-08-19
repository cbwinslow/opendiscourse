"""adopt canonical documents

Revision ID: d7a4e1c9b265
Revises: f9d2a6c4e183
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "d7a4e1c9b265"
down_revision: Union[str, Sequence[str], None] = "f9d2a6c4e183"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded canonical documents and bill links."""


def downgrade() -> None:
    """Retain canonical documents at the prior adoption marker."""
