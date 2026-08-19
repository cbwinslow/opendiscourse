"""Real PostgreSQL regression tests for the catalog SQLModel/Alembic foundation."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import select, text

from opendiscourse_research.browser import basket, get_resource, search, toggle, upsert_fields
from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, engine, session
from opendiscourse_research.models.catalog import Resource
from opendiscourse_research.repositories.catalog import (
    cache_fred_records,
    delete_resources_prefix,
    resource_ids,
    upsert_resource,
)


def _psycopg_url(url: str) -> str:
    """Normalize testcontainers' SQLAlchemy URL for the project's psycopg client."""
    return url.replace("postgresql+psycopg2://", "postgresql://", 1)


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    """Provide CI's PostGIS service or a local disposable PostGIS instance."""
    original_url = settings.database_url
    external_url = os.environ.get("OPENDISCOURSE_TEST_DATABASE_URL")
    if external_url:
        settings.database_url = external_url
        apply_migrations()
        sync_inventory()
        try:
            yield
        finally:
            settings.database_url = original_url
        return

    postgres = pytest.importorskip("testcontainers.postgres")
    with postgres.PostgresContainer(
        "postgis/postgis:17-3.5",
        username="test",
        password="test",
        dbname="test",
    ) as container:
        settings.database_url = _psycopg_url(container.get_connection_url())
        apply_migrations()
        sync_inventory()
        try:
            yield
        finally:
            settings.database_url = original_url
            _engine.cache_clear()


def test_catalog_baseline_and_search_indexes(catalog_database: None) -> None:
    """Legacy bootstrap stamps Alembic and exposes the intended search indexes."""
    with engine().connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        indexes = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'catalog' AND tablename = 'resource'"
                )
            )
        }
        extensions = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT extname FROM pg_extension "
                    "WHERE extname IN ('pg_trgm', 'unaccent')"
                )
            )
        }

    assert revision == "d207df35ca10"
    assert {"pg_trgm", "unaccent"} <= extensions
    assert {"resource_title_trgm_idx", "resource_fts_idx"} <= indexes


def test_resource_upserts_are_idempotent_and_search_indexes_are_usable(
    catalog_database: None,
) -> None:
    """Use real PostgreSQL upserts and plans rather than mocking SQLAlchemy."""
    key = "test:persistence-foundation"
    delete_resources_prefix("fred.series", "test:")
    upsert_resource(
        "fred.series",
        key,
        "series",
        "Initial income series",
        "first version",
        2024,
        {"version": 1},
    )
    upsert_resource(
        "fred.series",
        key,
        "series",
        "Updated income series",
        "second version",
        2024,
        {"version": 2},
    )
    cache_fred_records(
        [{"id": "test:fred-search", "title": "Income search series", "notes": "cached"}],
        {"method": "search", "query": "income"},
    )

    with session() as active_session:
        resources = list(
            active_session.scalars(
                select(Resource).where(Resource.resource_key.like("test:%"))
            )
        )

    assert len(resources) == 2
    updated = next(row for row in resources if row.resource_key == key)
    assert updated.title == "Updated income series"
    assert updated.metadata_ == {"version": 2}
    assert str(updated.resource_id) in resource_ids("fred.series", 2024, "series")
    upsert_fields(
        str(updated.resource_id),
        [{"id": "VALUE", "label": "Value", "concept": "Test value", "type": "number"}],
    )
    detail = get_resource(str(updated.resource_id))
    assert detail["metadata"] == {"version": 2}
    assert detail["fields"][0]["field_key"] == "VALUE"
    assert key in {row["resource_key"] for row in search("fred.series", "updated income")}
    assert toggle("test-persistence-foundation", str(updated.resource_id)) is True
    assert basket("test-persistence-foundation")[0]["resource_key"] == key
    assert toggle("test-persistence-foundation", str(updated.resource_id)) is False

    with engine().begin() as connection:
        connection.execute(text("SET LOCAL enable_seqscan = off"))
        trigram_plan = "\n".join(
            row[0]
            for row in connection.execute(
                text(
                    "EXPLAIN (COSTS OFF) SELECT resource_id FROM catalog.resource "
                    "WHERE title ILIKE '%income%'"
                )
            )
        )
        fts_plan = "\n".join(
            row[0]
            for row in connection.execute(
                text(
                    "EXPLAIN (COSTS OFF) SELECT resource_id FROM catalog.resource "
                    "WHERE to_tsvector('english', coalesce(resource_key, '') || ' ' || "
                    "coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || "
                    "coalesce(universe, '') || ' ' || coalesce(resource_type, '') || ' ' || "
                    "coalesce(metadata::text, '')) @@ websearch_to_tsquery('english', 'income')"
                )
            )
        )

    assert "resource_title_trgm_idx" in trigram_plan
    assert "resource_fts_idx" in fts_plan
    delete_resources_prefix("fred.series", "test:")
