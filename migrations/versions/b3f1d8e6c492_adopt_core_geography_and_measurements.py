"""adopt core geography and measurements

Revision ID: b3f1d8e6c492
Revises: e6c9d2f41a85
Create Date: 2026-08-19
"""

from typing import Sequence, Union


revision: str = "b3f1d8e6c492"
down_revision: Union[str, Sequence[str], None] = "e6c9d2f41a85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adopt legacy-seeded shared geography and measurement primitives."""


def downgrade() -> None:
    """Retain shared legacy primitives at the prior adoption marker."""
