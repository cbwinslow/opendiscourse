"""Alembic environment restricted to the SQLModel-owned catalog schema."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from opendiscourse_research.config import settings
from opendiscourse_research.models import catalog  # noqa: F401 - register metadata
from sqlmodel import SQLModel

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1),
)
target_metadata = SQLModel.metadata


def include_name(name: str | None, type_: str, parent_names: dict[str, str]) -> bool:
    """Reflect only catalog schema objects during migration autogeneration."""
    if type_ == "schema":
        return name == "catalog"
    return True


def include_object(object_: object, name: str | None, type_: str, reflected: bool, compare_to: object | None) -> bool:
    """Keep cross-schema reference stubs and unrelated reflected tables out."""
    if getattr(object_, "info", {}).get("alembic_exclude", False):
        return False
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    """Generate migration SQL without a database connection."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run catalog migrations against the configured PostgreSQL database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
