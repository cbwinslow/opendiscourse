"""baseline mapped persistence schema

Revision ID: d207df35ca10
Revises: 
Create Date: 2026-08-19 04:16:49.591165
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "d207df35ca10"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
BASELINE_DDL = (
    Path(__file__).resolve().parents[1] / "baseline" / "d207df35ca10.sql"
)
INDEX_TABLE = re.compile(r"^CREATE (?:UNIQUE )?INDEX \S+ ON (\S+)")


def upgrade() -> None:
    """Create the complete mapped schema for a new OpenDiscourse database."""
    existing_tables: set[str] = set()
    if not op.get_context().as_sql:
        inspector = inspect(op.get_bind())
        existing_tables = {
            f"{schema}.{table}"
            for schema in ("catalog", "core", "fact", "ingest", "stage")
            for table in inspector.get_table_names(schema=schema)
        }
    for statement in BASELINE_DDL.read_text().split(";\n\n"):
        normalized = statement.strip()
        if not normalized:
            continue
        if normalized.startswith("CREATE TABLE "):
            table_name = normalized.split()[2]
            if table_name in existing_tables:
                continue
        index_table = INDEX_TABLE.match(normalized)
        if index_table and index_table.group(1) in existing_tables:
            continue
        op.execute(statement)


def downgrade() -> None:
    """Keep legacy-seeded schemas intact when removing the adoption marker."""
