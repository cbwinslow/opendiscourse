from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import psycopg
from alembic import command
from alembic.config import Config
from psycopg.rows import dict_row
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session

from .config import settings

ROOT = Path(__file__).resolve().parents[2]
CATALOG_BASELINE_REVISION = "d207df35ca10"


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def _sqlalchemy_url(database_url: str) -> str:
    """Translate a psycopg DSN to SQLAlchemy's psycopg dialect URL."""
    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return str(url)


@lru_cache
def _engine(database_url: str) -> Engine:
    """Create one pooled engine for a resolved database URL."""
    return create_engine(database_url, pool_pre_ping=True)


def engine() -> Engine:
    """Return the engine for the current environment-backed database URL."""
    return _engine(_sqlalchemy_url(settings.database_url))


@contextmanager
def session() -> Iterator[Session]:
    """Provide a transactional SQLModel session for migrated persistence modules."""
    with Session(engine()) as active_session:
        try:
            yield active_session
            active_session.commit()
        except Exception:
            active_session.rollback()
            raise


def _alembic_config() -> Config:
    """Build Alembic configuration using the same environment-backed database URL."""
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("sqlalchemy.url", str(engine().url))
    return config


def apply_migrations() -> None:
    """Bootstrap legacy SQL, then adopt and advance catalog Alembic revisions."""
    with connect() as conn:
        for path in sorted((ROOT / "sql").glob("*.sql")):
            with conn.cursor() as cur:
                cur.execute(path.read_text())
            conn.commit()

    config = _alembic_config()
    if not inspect(engine()).has_table("alembic_version"):
        command.stamp(config, CATALOG_BASELINE_REVISION)
    command.upgrade(config, "head")
