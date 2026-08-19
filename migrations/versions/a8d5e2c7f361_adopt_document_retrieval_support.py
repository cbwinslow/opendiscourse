"""adopt document retrieval support

Revision ID: a8d5e2c7f361
Revises: f1c7e3a9d582
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "a8d5e2c7f361"
down_revision: Union[str, Sequence[str], None] = "f1c7e3a9d582"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded document chunks and portable embeddings."""


def downgrade() -> None:
    """Retain document retrieval support at the prior adoption marker."""
