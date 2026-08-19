"""baseline mapped persistence schema

Revision ID: d207df35ca10
Revises: 
Create Date: 2026-08-19 04:16:49.591165
"""

from collections.abc import Sequence

from alembic import op
from sqlmodel import SQLModel

from opendiscourse_research.models import catalog, core, ingest, stage  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "d207df35ca10"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the complete mapped schema for a new OpenDiscourse database."""
    for extension in ("postgis", "pgcrypto", "pg_trgm", "unaccent"):
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")
    for schema in ("catalog", "core", "fact", "ingest", "stage", "leg", "mart"):
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    SQLModel.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Keep legacy-seeded schemas intact when removing the adoption marker."""
