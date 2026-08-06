from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import settings

ROOT = Path(__file__).resolve().parents[2]


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def apply_migrations() -> None:
    with connect() as conn:
        for path in sorted((ROOT / "sql").glob("*.sql")):
            with conn.cursor() as cur:
                cur.execute(path.read_text())
            conn.commit()
