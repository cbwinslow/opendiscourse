"""One PostGIS server and one migrated template for the database tests.

Postgres copies a database with ``CREATE DATABASE ... TEMPLATE``. The copy is
a file-level clone, so each test module gets a private database without
booting another server or replaying the schema. A clone cannot be made while
anything is connected to the template, which is a Postgres rule, not a pytest
rule.

Locally the server is one throwaway PostGIS container. In CI it is the
PostGIS service already named by ``OPENDISCOURSE_TEST_DATABASE_URL``. Parallel
pytest workers stay off until each worker has its own template: two clones of
the same template at the same time will fail.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg
from sqlalchemy.engine import make_url

from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, engine

_NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")


@dataclass
class _Cluster:
    admin_url: str
    template_name: str
    container: object | None
    clones: int = 0


_cluster: _Cluster | None = None
_starts = 0


def database_url_for(url: str, database: str) -> str:
    """Return ``url`` with only its database name replaced."""
    _validate_name(database)
    return make_url(url).set(database=database).render_as_string(hide_password=False)


def cluster_start_count() -> int:
    """How many times this process has started the shared test server."""
    return _starts


@contextmanager
def cloned_database() -> Iterator[str]:
    """Point the application at a private copy of the migrated template.

    Yields the copy's database name. The caller's ``settings.database_url`` is
    restored even when the body fails, and the copy is then dropped.
    """
    cluster = _ensure_cluster()
    name = f"od_clone_{os.getpid()}_{cluster.clones}"
    cluster.clones += 1
    _validate_name(name)
    _terminate(cluster.admin_url, cluster.template_name)
    _create(cluster.admin_url, name, cluster.template_name)
    original = settings.database_url
    settings.database_url = database_url_for(cluster.admin_url, name)
    _release_engines()
    try:
        yield name
    finally:
        _release_engines()
        settings.database_url = original
        _release_engines()
        _drop(cluster.admin_url, name)


def stop_cluster() -> None:
    """Drop the template and stop the throwaway server, if this process started one."""
    global _cluster
    cluster = _cluster
    _cluster = None
    if cluster is None:
        return
    _release_engines()
    _drop(cluster.admin_url, cluster.template_name)
    container = cluster.container
    if container is not None:
        container.stop()


def _ensure_cluster() -> _Cluster:
    global _cluster, _starts
    if _cluster is not None:
        return _cluster
    external = os.environ.get("OPENDISCOURSE_TEST_DATABASE_URL")
    container = None
    if external:
        admin_url = database_url_for(external, "postgres")
    else:
        import pytest

        postgres = pytest.importorskip("testcontainers.postgres")
        container = postgres.PostgresContainer(
            "postgis/postgis:17-3.5",
            username="test",
            password="test",
            dbname="postgres",
        )
        container.start()
        admin_url = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)
    template_name = f"od_tmpl_{os.getpid()}"
    _validate_name(template_name)
    try:
        _drop(admin_url, template_name)
        _create(admin_url, template_name, template=None)
        original = settings.database_url
        settings.database_url = database_url_for(admin_url, template_name)
        _release_engines()
        try:
            apply_migrations()
        finally:
            _release_engines()
            settings.database_url = original
            _release_engines()
    except Exception:
        if container is not None:
            container.stop()
        raise
    _starts += 1
    _cluster = _Cluster(admin_url=admin_url, template_name=template_name, container=container)
    return _cluster


def _validate_name(name: str) -> None:
    if _NAME.fullmatch(name) is None:
        raise ValueError(f"refusing database name {name!r}")


def _release_engines() -> None:
    """Close pooled SQLAlchemy connections so a database can be copied or dropped."""
    engine().dispose()
    _engine.cache_clear()


def _connect_admin(admin_url: str) -> psycopg.Connection:
    return psycopg.connect(admin_url, autocommit=True)


def _create(admin_url: str, name: str, template: str | None) -> None:
    statement = f'CREATE DATABASE "{name}"'
    if template is not None:
        _validate_name(template)
        statement += f' TEMPLATE "{template}"'
    with _connect_admin(admin_url) as conn:
        conn.execute(statement)


def _drop(admin_url: str, name: str) -> None:
    _validate_name(name)
    _terminate(admin_url, name)
    with _connect_admin(admin_url) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _terminate(admin_url: str, database: str) -> None:
    with _connect_admin(admin_url) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (database,),
        )
