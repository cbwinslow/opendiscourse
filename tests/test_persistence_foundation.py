"""Real PostgreSQL regression tests for the catalog SQLModel/Alembic foundation."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from opendiscourse_research.browser import (
    basket,
    get_resource,
    search,
    sync_acs,
    sync_bls,
    sync_fred,
    toggle,
    upsert_fields,
)
from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, engine, session
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion import census as census_ingestion
from opendiscourse_research.ingestion.base import IngestionRun
from opendiscourse_research.models.catalog import CatalogSnapshot, DatasetField, Resource, SnapshotResource
from opendiscourse_research.models.ingest import cursor_table, raw_payload_table, run_table
from opendiscourse_research.plans import due_plans, load_plans
from opendiscourse_research.registry import status as registry_status
from opendiscourse_research.repositories.catalog import (
    cache_fred_records,
    claim_discovery,
    delete_resources_prefix,
    discovery,
    resource_ids,
    save_discovery,
    upsert_resource,
)
from opendiscourse_research.providers import census


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


def test_acs_sync_preserves_artifact_backed_snapshot_provenance(
    catalog_database: None, tmp_path: Path
) -> None:
    """ACS promotion is idempotent and retains its immutable discovery artifact."""
    original_data_root = settings.data_root
    settings.data_root = tmp_path / "data"
    try:
        manifest_path = tmp_path / "meta" / "acs" / "2030" / "tables.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            '{"tables": [{"id": "B01001", "title": "Sex by Age", "product": "detailed", '
            '"universe": "Total population", "one_year": true, "five_year": true}]}'
        )
        register_local(
            ArtifactSpec(
                dataset_id="census.acs_5",
                artifact_key="tables-2030",
                url="https://example.test/acs/2030/tables.json",
                filename="tables-2030.json",
            ),
            manifest_path,
        )

        assert sync_acs(2030) == 1
        assert sync_acs(2030) == 1

        with session() as active_session:
            resource = active_session.scalar(
                select(Resource).where(
                    Resource.dataset_id == "census.acs_5", Resource.resource_key == "2030:B01001"
                )
            )
            snapshot = active_session.scalar(
                select(CatalogSnapshot).where(
                    CatalogSnapshot.dataset_id == "census.acs_5",
                    CatalogSnapshot.metadata_["year"].astext == "2030",
                )
            )
            assert snapshot is not None
            memberships = list(
                active_session.scalars(
                    select(SnapshotResource).where(SnapshotResource.snapshot_id == snapshot.snapshot_id)
                )
            )

        assert resource is not None
        assert resource.metadata_["table_id"] == "B01001"
        assert snapshot.artifact_id is not None
        assert len(memberships) == 1
        assert memberships[0].resource_id == resource.resource_id
    finally:
        settings.data_root = original_data_root


def test_curated_provider_syncs_record_idempotent_catalog_snapshots(
    catalog_database: None,
) -> None:
    """Curated manifests use the common SQLAlchemy resource and snapshot path."""
    fred = sync_fred()
    bls = sync_bls()
    assert sync_fred() == fred
    assert sync_bls() == bls

    with session() as active_session:
        fred_snapshot = active_session.scalar(
            select(CatalogSnapshot).where(
                CatalogSnapshot.dataset_id == "fred.series",
                CatalogSnapshot.metadata_["kind"].astext == "curated_series_manifest",
            )
        )
        bls_snapshots = list(
            active_session.scalars(
                select(CatalogSnapshot).where(
                    CatalogSnapshot.dataset_id.in_(("bls.cpi", "bls.laus")),
                    CatalogSnapshot.metadata_["kind"].astext == "curated_series_manifest",
                )
            )
        )

    assert fred["resources"] > 0
    assert bls["resources"] > 0
    assert fred_snapshot is not None
    assert len(bls_snapshots) == 2


def test_census_api_catalog_sync_links_resources_to_the_ingested_payload(
    catalog_database: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Census API discovery retains source payload provenance through SQLAlchemy writes."""
    payload = {
        "dataset": [
            {
                "identifier": "https://api.census.gov/data/2030/acs/acs5",
                "title": "ACS 5-Year sample",
                "description": "A test offering",
                "c_dataset": ["acs5"],
                "c_vintage": "2030",
                "distribution": [
                    {"format": "API", "accessURL": "https://api.census.gov/data/2030/acs/acs5"}
                ],
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json=payload)

    monkeypatch.setattr(
        census, "client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = census.sync_catalog()
    repeat = census.sync_catalog()

    with session() as active_session:
        resource = active_session.scalar(
            select(Resource).where(
                Resource.dataset_id == "census.api_catalog",
                Resource.resource_key == payload["dataset"][0]["identifier"],
            )
        )
        snapshot = active_session.scalar(
            select(CatalogSnapshot).where(
                CatalogSnapshot.dataset_id == "census.api_catalog",
                CatalogSnapshot.metadata_["kind"].astext == "census_data_api_catalog",
            )
        )

    assert result["resources"] == 1
    assert repeat["resources"] == 1
    assert repeat["payload_id"] != result["payload_id"]
    assert resource is not None
    assert resource.release_year == 2030
    assert resource.metadata_["source_payload_id"] == repeat["payload_id"]
    assert snapshot is not None


def test_acs_field_catalog_uses_batched_sqlalchemy_upserts(
    catalog_database: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Official ACS shell fields retain labels and are safe to load repeatedly."""
    shell = tmp_path / "ACS2030_Table_Shells.txt"
    shell.write_text(
        "Unique ID|Label|Title|Universe|Type|Line|Indent\n"
        "B01001_001|Total:|Sex by Age|Total population|N|1|0\n"
    )
    monkeypatch.setattr(census_ingestion, "remote_size", lambda _: 1)
    monkeypatch.setattr(census_ingestion, "storage_preview", lambda _: {"approved": True})
    monkeypatch.setattr(census_ingestion, "download", lambda _: shell)

    assert census_ingestion.load_acs_field_catalog(2030) == 2
    assert census_ingestion.load_acs_field_catalog(2030) == 2
    with session() as active_session:
        fields = list(
            active_session.scalars(
                select(DatasetField).where(
                    DatasetField.dataset_id == "census.acs_5_bulk",
                    DatasetField.field_id.in_(("B01001_E001", "B01001_M001")),
                )
            )
        )

    assert len(fields) == 2
    assert {field.label for field in fields} == {"Total:"}
    assert {field.metadata_["table_id"] for field in fields} == {"B01001"}


def test_catalog_discovery_claims_are_resumable_and_exclusive(
    catalog_database: None,
) -> None:
    """A discovery worker may resume after saving progress but not double-claim live work."""
    identifier = "test-persistence-foundation-discovery"
    assert claim_discovery(identifier, "fred.series") is not None
    assert claim_discovery(identifier, "fred.series") is None
    save_discovery(
        identifier,
        "fred.series",
        "paused",
        {"offset": 10},
        {"records": 10},
    )
    claimed = claim_discovery(identifier, "fred.series")
    assert claimed is not None
    saved = discovery(identifier)
    assert saved is not None
    assert saved["state"] == "running"
    assert saved["cursor"] == {"offset": 10}


def test_due_plans_reads_typed_ingestion_cursors(catalog_database: None) -> None:
    """Plan scheduling reads legacy ingestion cursors through the typed table reference."""
    plan = load_plans()[0]
    table = cursor_table()
    statement = insert(table).values(
        plan_id=plan["id"], cursor={"last_count": 1}, updated_at=datetime(2000, 1, 1, tzinfo=UTC)
    )
    with session() as active_session:
        active_session.execute(
            statement.on_conflict_do_update(
                index_elements=(table.c.plan_id,),
                set_={"cursor": statement.excluded.cursor, "updated_at": statement.excluded.updated_at},
            )
        )

    assert plan in due_plans(datetime(2030, 1, 1, tzinfo=UTC))


def test_ingestion_run_persists_typed_run_and_raw_payload_evidence(
    catalog_database: None,
) -> None:
    """Run bookkeeping remains provenance-rich while fact loaders retain their connection."""
    response = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={"source": "test"},
        request=httpx.Request("GET", "https://example.test/payload"),
    )
    with IngestionRun("fred.series", {"test": True}, mode="plan") as run:
        payload_id = run.store_payload(response, {"source": "test"})
        run.record_count = 3
        run_id = run.run_id

    with session() as active_session:
        stored_run = active_session.execute(
            select(run_table().c.status, run_table().c.record_count).where(
                run_table().c.run_id == run_id
            )
        ).mappings().one()
        payload = active_session.execute(
            select(raw_payload_table().c.run_id, raw_payload_table().c.payload).where(
                raw_payload_table().c.payload_id == payload_id
            )
        ).mappings().one()

    assert stored_run == {"status": "succeeded", "record_count": 3}
    assert payload == {"run_id": run_id, "payload": {"source": "test"}}


def test_registry_status_reads_catalog_through_sqlalchemy(catalog_database: None) -> None:
    """Readiness reporting returns every registered dataset without raw catalog SQL."""
    rows = registry_status()
    assert rows
    assert {row["dataset_id"] for row in rows} >= {"fred.series", "census.acs_5"}
    assert {row["state"] for row in rows} <= {"ready", "pending_adapter"}
