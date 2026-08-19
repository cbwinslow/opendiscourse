"""Real PostgreSQL regression tests for the catalog SQLModel/Alembic foundation."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from alembic import command
from geoalchemy2 import WKTElement
from sqlalchemy import func, select, text
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
from opendiscourse_research.censushealth import census_health
from opendiscourse_research import congresshealth
from opendiscourse_research.congresshealth import recover_stale_congressional_runs
from opendiscourse_research.config import settings
from opendiscourse_research.db import _alembic_config, _engine, apply_migrations, engine, session
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion import census as census_ingestion
from opendiscourse_research.ingestion import bls as bls_ingestion
from opendiscourse_research.ingestion import congress as congress_ingestion
from opendiscourse_research.ingestion import fred as fred_ingestion
from opendiscourse_research.ingestion import treasury as treasury_ingestion
from opendiscourse_research.ingestion.base import IngestionRun
from opendiscourse_research.identityexceptions import unresolved_congressional_identities
from opendiscourse_research.ingestion.tiger_load import _artifact as tiger_artifact
from opendiscourse_research.ingestion.acs_load import _artifact as acs_artifact
from opendiscourse_research.ingestion.cbp_load import _artifact as cbp_artifact
from opendiscourse_research.ingestion.dhc_load import _artifact as dhc_artifact
from opendiscourse_research.ingestion.pep_load import _artifact as pep_artifact
from opendiscourse_research.ingestion.fec_bulk import _registered_artifacts as fec_artifacts
from opendiscourse_research.models.catalog import (
    CatalogSnapshot,
    DatasetField,
    Resource,
    SnapshotResource,
    artifact_table,
)
from opendiscourse_research.models.core import (
    bill_action_table,
    bill_committee_table,
    bill_document_table,
    bill_identifier_table,
    bill_sponsorship_table,
    bill_subject_table,
    bill_table,
    document_table,
    geography_boundary_table,
    geography_table,
    jurisdiction_table,
    legislative_session_table,
    measurement_table,
    person_table,
)
from opendiscourse_research.models.ingest import (
    cursor_table,
    identity_exception_table,
    raw_payload_table,
    resume_cursor_table,
    run_table,
)
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
from opendiscourse_research.repositories.legislation import (
    ensure_us_legislative_session,
    get_artifact,
    get_resume_cursor,
    loaded_artifact_members,
    record_vote_identity_exceptions,
    register_artifact,
    resolve_bill_sponsorship_people,
    save_resume_cursor,
    save_billstatus_bill,
    upsert_congress_person,
)
from opendiscourse_research.providers import census
from opendiscourse_research.providers.census import sync_acs_bulk_packages


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


def test_adopted_schemas_and_search_indexes(catalog_database: None) -> None:
    """Legacy bootstrap advances Alembic through adopted schema revisions."""
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

    assert revision == "c5a7e2d8b419"
    assert {"pg_trgm", "unaccent"} <= extensions
    assert {"resource_title_trgm_idx", "resource_fts_idx"} <= indexes


def test_alembic_adoptions_can_downgrade_and_reupgrade(
    catalog_database: None,
) -> None:
    """Adoption revisions are reversible over the legacy-seeded schemas."""
    config = _alembic_config()
    command.downgrade(config, "base")
    try:
        with engine().connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM catalog.resource")).scalar_one() >= 0
            assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 0
    finally:
        command.upgrade(config, "head")

    with engine().connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "c5a7e2d8b419"


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
            artifact = active_session.execute(
                select(
                    artifact_table().c.status,
                    artifact_table().c.local_path,
                    artifact_table().c.checksum_sha256,
                    artifact_table().c.metadata,
                ).where(
                    artifact_table().c.dataset_id == "census.acs_5",
                    artifact_table().c.artifact_key == "tables-2030",
                )
            ).mappings().one()
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
        assert artifact["status"] == "downloaded"
        assert artifact["local_path"] == str(manifest_path.resolve())
        assert artifact["checksum_sha256"]
        assert artifact["metadata"] == {}
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


def test_acs_ingestion_upserts_geography_and_measurements_with_sqlalchemy(
    catalog_database: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Census response retains geography, values, and payload lineage on repeat runs."""
    payload = [
        ["NAME", "B01001_001", "state", "county"],
        ["Example County", "42", "01", "001"],
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json=payload)

    monkeypatch.setattr(settings, "census_api_key", "test-key")
    monkeypatch.setattr(
        census_ingestion, "client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert census_ingestion.ingest_acs(2030, "01", ["B01001_001"]) == 1
    assert census_ingestion.ingest_acs(2030, "01", ["B01001_001"]) == 1

    geography = geography_table()
    measurement = measurement_table()
    with session() as active_session:
        geography_row = active_session.execute(
            select(geography.c.geography_id, geography.c.name).where(
                geography.c.geography_type == "county", geography.c.geoid == "01001"
            )
        ).mappings().one()
        measurements = list(
            active_session.execute(
                select(
                    measurement.c.value_numeric,
                    measurement.c.value_text,
                    measurement.c.source_payload_id,
                ).where(
                    measurement.c.dataset_id == "census.acs_5",
                    measurement.c.field_id == "B01001_001",
                    measurement.c.geography_id == geography_row["geography_id"],
                    measurement.c.period_start == datetime(2030, 1, 1, tzinfo=UTC).date(),
                )
            ).mappings()
        )

    assert geography_row["name"] == "Example County"
    assert len(measurements) == 1
    assert measurements[0]["value_numeric"] == 42
    assert measurements[0]["value_text"] == "42"
    assert measurements[0]["source_payload_id"] is not None


def test_fred_ingestion_upserts_measurements_with_sqlalchemy(
    catalog_database: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FRED observations retain null-geography uniqueness and source payload lineage."""
    payload = {
        "observations": [
            {"date": "2030-01-01", "realtime_start": "2030-01-02", "value": "3.5"},
            {"date": "2030-02-01", "realtime_start": "2030-02-02", "value": "."},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json=payload)

    monkeypatch.setattr(settings, "fred_api_key", "test-key")
    monkeypatch.setattr(
        fred_ingestion, "client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert fred_ingestion.ingest_series("TEST_FRED") == 2
    assert fred_ingestion.ingest_series("TEST_FRED") == 2

    table = measurement_table()
    with session() as active_session:
        rows = list(
            active_session.execute(
                select(
                    table.c.value_numeric,
                    table.c.geography_id,
                    table.c.flags,
                    table.c.source_payload_id,
                )
                .where(table.c.dataset_id == "fred.series", table.c.field_id == "TEST_FRED")
                .order_by(table.c.period_start)
            ).mappings()
        )

    assert len(rows) == 2
    assert rows[0]["value_numeric"] == 3.5
    assert rows[1]["value_numeric"] is None
    assert all(row["geography_id"] is None for row in rows)
    assert all(row["flags"] == {"source": "FRED"} for row in rows)
    assert all(row["source_payload_id"] is not None for row in rows)


def test_bls_ingestion_upserts_monthly_measurements_with_sqlalchemy(
    catalog_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BLS ignores annual averages and safely replaces monthly observations."""
    payload = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {
            "series": [
                {
                    "data": [
                        {"year": "2030", "period": "M01", "value": "2.5"},
                        {"year": "2030", "period": "M13", "value": "9.9"},
                    ]
                }
            ]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json=payload)

    monkeypatch.setattr(
        bls_ingestion, "client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert bls_ingestion.ingest_series("bls.cpi", "TEST_BLS", 2030, 2030) == 1
    assert bls_ingestion.ingest_series("bls.cpi", "TEST_BLS", 2030, 2030) == 1

    table = measurement_table()
    with session() as active_session:
        rows = list(
            active_session.execute(
                select(table.c.value_numeric, table.c.flags, table.c.source_payload_id).where(
                    table.c.dataset_id == "bls.cpi", table.c.field_id == "TEST_BLS"
                )
            ).mappings()
        )

    assert len(rows) == 1
    assert rows[0]["value_numeric"] == 2.5
    assert rows[0]["flags"] == {"source": "BLS"}
    assert rows[0]["source_payload_id"] is not None


def test_tiger_artifact_lookup_uses_typed_immutable_evidence(
    catalog_database: None, tmp_path: Path
) -> None:
    """TIGER staging resolves only registered downloaded artifacts via the shared mapping."""
    source = tmp_path / "tiger.zip"
    source.write_bytes(b"test tiger artifact")
    register_local(
        ArtifactSpec(
            dataset_id="census.tiger",
            artifact_key="test-tiger-typed-artifact",
            url="https://example.test/tiger.zip",
            filename="tiger.zip",
        ),
        source,
    )

    artifact = tiger_artifact("test-tiger-typed-artifact")
    assert artifact["artifact_id"]
    assert artifact["local_path"] == str(source.resolve())


def test_loaded_legislation_artifact_members_use_typed_identifier_lineage(
    catalog_database: None,
) -> None:
    """Completed archive members are read from canonical identifier provenance."""
    artifact = register_artifact(
        "congress.govinfo_billstatus",
        "https://example.test/members.zip",
        "/tmp/members.zip",
        "test-member-lineage-artifact",
    )
    bill = bill_table()
    identifiers = bill_identifier_table()
    with session() as active_session:
        bill_id = active_session.execute(
            insert(bill)
            .values(
                jurisdiction="us",
                legislative_session="130",
                bill_type="hr",
                bill_number="99999",
                title="Test bill",
            )
            .on_conflict_do_update(
                index_elements=(bill.c.jurisdiction, bill.c.legislative_session, bill.c.bill_type, bill.c.bill_number),
                set_={"title": "Test bill"},
            )
            .returning(bill.c.bill_id)
        ).scalar_one()
        for external_id, metadata in (
            ("member-1", {"member_name": "BILLSTATUS-130hr1.xml"}),
            ("member-2", {"member_name": "BILLSTATUS-130hr2.xml"}),
            ("other", {"not_member": True}),
        ):
            active_session.execute(
                insert(identifiers)
                .values(
                    bill_id=bill_id,
                    namespace="govinfo.package",
                    external_id=f"test-{external_id}",
                    source_artifact_id=artifact["artifact_id"],
                    metadata=metadata,
                )
                .on_conflict_do_update(
                    index_elements=(identifiers.c.namespace, identifiers.c.external_id),
                    set_={"metadata": metadata, "source_artifact_id": artifact["artifact_id"]},
                )
            )

    assert loaded_artifact_members(str(artifact["artifact_id"])) == {
        "BILLSTATUS-130hr1.xml",
        "BILLSTATUS-130hr2.xml",
    }


def test_openstates_resume_and_identity_evidence_use_typed_mappings(
    catalog_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Checkpoint and unresolved-voter evidence retain source/run lineage idempotently."""
    artifact = register_artifact(
        "openstates.legislation",
        "https://example.test/openstates.json",
        "/tmp/openstates.json",
        "test-openstates-evidence-artifact",
    )
    with IngestionRun("openstates.legislation", {"test": "typed evidence"}) as run:
        assert run.run_id is not None
        saved = save_resume_cursor(
            "openstates.legislation",
            "voteevent:130",
            {"ocd_id": "ocd-vote/130"},
            str(artifact["artifact_id"]),
            str(run.run_id),
            "running",
        )
        assert saved == {"cursor": {"ocd_id": "ocd-vote/130"}, "state": "running"}
        assert record_vote_identity_exceptions(
            130,
            str(artifact["artifact_id"]),
            str(run.run_id),
            ["ocd-person/a", "ocd-person/a", None],
        ) == 2
        assert record_vote_identity_exceptions(
            130,
            str(artifact["artifact_id"]),
            str(run.run_id),
            ["ocd-person/a", None],
        ) == 2

    checkpoint = get_resume_cursor("openstates.legislation", "voteevent:130")
    assert checkpoint is not None
    assert checkpoint["cursor"] == {"ocd_id": "ocd-vote/130"}
    assert checkpoint["state"] == "running"

    exceptions = identity_exception_table()
    checkpoints = resume_cursor_table()
    with session() as active_session:
        rows = list(
            active_session.execute(
                select(exceptions.c.external_id, exceptions.c.reason, exceptions.c.reference_count)
                .where(exceptions.c.run_id == run.run_id)
                .order_by(exceptions.c.external_id)
            ).mappings()
        )
        checkpoint_artifact = active_session.execute(
            select(checkpoints.c.source_artifact_id).where(
                checkpoints.c.dataset_id == "openstates.legislation",
                checkpoints.c.cursor_key == "voteevent:130",
            )
        ).scalar_one()

    assert rows == [
        {
            "external_id": "<missing>",
            "reason": "missing_ocd_voter_id",
            "reference_count": 2,
        },
        {
            "external_id": "ocd-person/a",
            "reason": "no_canonical_person_identifier",
            "reference_count": 3,
        },
    ]
    assert str(checkpoint_artifact) == str(artifact["artifact_id"])

    monkeypatch.setattr(settings, "data_root", str(tmp_path / "data"))
    report = unresolved_congressional_identities()
    unresolved = {
        (row["external_id"], row["reason"]): row["references"]
        for row in report["exceptions"]
    }
    assert unresolved[("<missing>", "missing_ocd_voter_id")] == 2
    assert unresolved[("ocd-person/a", "no_canonical_person_identifier")] == 3
    assert Path(report["report"]).is_file()


def test_billstatus_graph_default_path_uses_typed_mappings(
    catalog_database: None,
) -> None:
    """BILLSTATUS graph persistence is provenance-preserving and idempotent via SQLAlchemy."""
    artifact = register_artifact(
        "congress.govinfo_billstatus",
        "https://example.test/billstatus.zip",
        "/tmp/billstatus.zip",
        "test-billstatus-graph-artifact",
    )
    legislative_session_id = ensure_us_legislative_session(
        131, source_artifact_id=str(artifact["artifact_id"])
    )
    bill_data = {
        "congress": 131,
        "bill_type": "hr",
        "bill_number": "4242",
        "title": "Test BILLSTATUS graph",
        "introduced_date": "2031-01-03",
        "latest_action_date": "2031-02-04",
        "latest_action": "Referred to committee",
        "identifiers": [
            {
                "namespace": "govinfo.package",
                "external_id": "BILLS-131hr4242ih",
                "source_url": "https://example.test/BILLS-131hr4242ih.xml",
                "metadata": {"member_name": "BILLS-131hr4242ih.xml"},
            }
        ],
        "actions": [
            {
                "action_date": "2031-02-04T00:00:00+00:00",
                "description": "Referred to committee",
                "classification": ["referral"],
                "source_ordinal": 1,
                "metadata": {"action": "first"},
            }
        ],
        "sponsorships": [
            {
                "member_namespace": "bioguide",
                "member_external_id": "T000001",
                "role": "sponsor",
                "metadata": {"sponsor": True},
            }
        ],
        "committees": [
            {
                "external_id": "HSAG",
                "name": "Agriculture",
                "chamber": "lower",
                "metadata": {"committee": True},
            }
        ],
        "subjects": [
            {
                "external_id": "1000",
                "label": "Agriculture",
                "metadata": {"subject": True},
            }
        ],
        "documents": [
            {
                "source_url": "https://example.test/BILLS-131hr4242ih.xml",
                "title": "Introduced in House",
                "published_at": "2031-01-03T00:00:00+00:00",
                "version_code": "ih",
                "metadata": {"document": True},
            }
        ],
    }

    bill_id = save_billstatus_bill(
        bill_data,
        legislative_session_id,
        source_artifact_id=str(artifact["artifact_id"]),
        source_member="BILLS-131hr4242ih.xml",
    )
    assert save_billstatus_bill(
        bill_data,
        legislative_session_id,
        source_artifact_id=str(artifact["artifact_id"]),
        source_member="BILLS-131hr4242ih.xml",
    ) == bill_id

    actions = bill_action_table()
    committees = bill_committee_table()
    documents = document_table()
    links = bill_document_table()
    identifiers = bill_identifier_table()
    sponsorships = bill_sponsorship_table()
    subjects = bill_subject_table()
    with session() as active_session:
        counts = {
            "identifiers": active_session.execute(
                select(func.count()).select_from(identifiers).where(identifiers.c.bill_id == bill_id)
            ).scalar_one(),
            "actions": active_session.execute(
                select(func.count()).select_from(actions).where(actions.c.bill_id == bill_id)
            ).scalar_one(),
            "sponsorships": active_session.execute(
                select(func.count()).select_from(sponsorships).where(sponsorships.c.bill_id == bill_id)
            ).scalar_one(),
            "committees": active_session.execute(
                select(func.count()).select_from(committees).where(committees.c.bill_id == bill_id)
            ).scalar_one(),
            "subjects": active_session.execute(
                select(func.count()).select_from(subjects).where(subjects.c.bill_id == bill_id)
            ).scalar_one(),
            "documents": active_session.execute(
                select(func.count())
                .select_from(links.join(documents, links.c.document_id == documents.c.document_id))
                .where(links.c.bill_id == bill_id)
            ).scalar_one(),
        }
        action_row = active_session.execute(
            select(actions.c.description, actions.c.source_artifact_id, actions.c.metadata).where(
                actions.c.bill_id == bill_id
            )
        ).mappings().one()

    assert counts == {
        "identifiers": 1,
        "actions": 1,
        "sponsorships": 1,
        "committees": 1,
        "subjects": 1,
        "documents": 1,
    }
    assert action_row["description"] == "Referred to committee"
    assert str(action_row["source_artifact_id"]) == str(artifact["artifact_id"])
    assert action_row["metadata"] == {"action": "first"}


def test_congress_api_bill_upsert_uses_typed_canonical_mapping(
    catalog_database: None,
) -> None:
    """Congress.gov bill identity upserts retain the legacy conflict-update semantics."""
    first = {
        "congress": 132,
        "type": "HR",
        "number": 7,
        "title": "Initial title",
        "introducedDate": "2032-01-03",
        "latestAction": {"actionDate": "2032-01-04", "text": "Introduced"},
    }
    updated = {
        **first,
        "title": None,
        "introducedDate": None,
        "latestAction": {"actionDate": "2032-01-05", "text": "Referred"},
    }
    with session() as active_session:
        congress_ingestion._upsert_bill(active_session, first, "unused-payload-id")
    with session() as active_session:
        congress_ingestion._upsert_bill(active_session, updated, "unused-payload-id")

    bill = bill_table()
    with session() as active_session:
        row = active_session.execute(
            select(
                bill.c.title,
                bill.c.introduced_date,
                bill.c.latest_action_date,
                bill.c.latest_action,
                bill.c.metadata,
            ).where(
                bill.c.jurisdiction == "us",
                bill.c.legislative_session == "132",
                bill.c.bill_type == "hr",
                bill.c.bill_number == "7",
            )
        ).mappings().one()

    assert row == {
        "title": None,
        "introduced_date": datetime(2032, 1, 3).date(),
        "latest_action_date": datetime(2032, 1, 5).date(),
        "latest_action": "Referred",
        "metadata": {"source": "congress.gov"},
    }


def test_congress_member_and_sponsorship_resolution_use_typed_mappings(
    catalog_database: None,
) -> None:
    """BioGuide identity is immutable while unresolved sponsorships link to it."""
    artifact = register_artifact(
        "congress.govinfo_billstatus",
        "https://example.test/member-source.zip",
        "/tmp/member-source.zip",
        "test-congress-member-artifact",
    )
    first_member = {
        "bioguideId": "T000002",
        "directOrderName": "Taylor Test",
        "firstName": "Taylor",
        "lastName": "Test",
    }
    person_id = upsert_congress_person(first_member)
    assert upsert_congress_person({**first_member, "directOrderName": "Changed Name"}) == person_id

    bill = bill_table()
    sponsorship = bill_sponsorship_table()
    people = person_table()
    with session() as active_session:
        bill_id = active_session.execute(
            insert(bill)
            .values(jurisdiction="us", legislative_session="133", bill_type="s", bill_number="8")
            .on_conflict_do_update(
                index_elements=(bill.c.jurisdiction, bill.c.legislative_session, bill.c.bill_type, bill.c.bill_number),
                set_={"title": None},
            )
            .returning(bill.c.bill_id)
        ).scalar_one()
        active_session.execute(
            insert(sponsorship).values(
                bill_id=bill_id,
                member_namespace="bioguide",
                member_external_id="T000002",
                role="sponsor",
                source_artifact_id=artifact["artifact_id"],
                metadata={},
            )
        )

    assert resolve_bill_sponsorship_people() == 1
    assert resolve_bill_sponsorship_people() == 0
    with session() as active_session:
        linked_person = active_session.execute(
            select(sponsorship.c.person_id).where(sponsorship.c.bill_id == bill_id)
        ).scalar_one()
        stored_name = active_session.execute(
            select(people.c.full_name).where(people.c.person_id == person_id)
        ).scalar_one()

    assert str(linked_person) == person_id
    assert stored_name == "Taylor Test"


def test_treasury_yield_curve_uses_typed_measurement_upserts(
    catalog_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treasury observations replace matching values and preserve raw-payload lineage."""
    csv_body = "Date,1 Mo,2 Mo,3 Mo\n01/02/2033,1.25,N/A,bad\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/csv"}, text=csv_body)

    monkeypatch.setattr(
        treasury_ingestion,
        "client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert treasury_ingestion.ingest_yield_curve(2033) == 1
    assert treasury_ingestion.ingest_yield_curve(2033) == 1

    measurement = measurement_table()
    with session() as active_session:
        rows = list(
            active_session.execute(
                select(
                    measurement.c.field_id,
                    measurement.c.value_numeric,
                    measurement.c.unit,
                    measurement.c.flags,
                    measurement.c.source_payload_id,
                ).where(
                    measurement.c.dataset_id == "treasury.yield_curve",
                    measurement.c.period_start == datetime(2033, 1, 2).date(),
                )
            ).mappings()
        )

    assert len(rows) == 1
    assert rows[0]["field_id"] == "1 Mo"
    assert rows[0]["value_numeric"] == 1.25
    assert rows[0]["unit"] == "percent"
    assert rows[0]["flags"] == {"curve_type": "daily_treasury_yield_curve"}
    assert rows[0]["source_payload_id"] is not None


def test_legislative_session_default_path_uses_typed_core_mappings(
    catalog_database: None,
) -> None:
    """US Congress sessions retain source artifact lineage through SQLAlchemy upserts."""
    artifact = register_artifact(
        "congress.govinfo_billstatus",
        "https://example.test/session.zip",
        "/tmp/session.zip",
        "test-legislative-session-artifact",
        metadata={"source": "test"},
    )
    session_id = ensure_us_legislative_session(
        130, source_artifact_id=str(artifact["artifact_id"]), metadata={"first": True}
    )
    assert ensure_us_legislative_session(
        130, source_artifact_id=str(artifact["artifact_id"]), metadata={"second": True}
    ) == session_id

    jurisdiction = jurisdiction_table()
    legislative_session = legislative_session_table()
    with session() as active_session:
        jurisdiction_row = active_session.execute(
            select(jurisdiction.c.name, jurisdiction.c.metadata).where(
                jurisdiction.c.jurisdiction_id == "ocd-jurisdiction/country:us/government"
            )
        ).mappings().one()
        session_row = active_session.execute(
            select(
                legislative_session.c.identifier,
                legislative_session.c.active,
                legislative_session.c.source_artifact_id,
                legislative_session.c.metadata,
            ).where(legislative_session.c.legislative_session_id == session_id)
        ).mappings().one()

    assert jurisdiction_row["name"] == "United States Congress"
    assert jurisdiction_row["metadata"] == {"country": "us"}
    assert session_row["identifier"] == "130"
    assert session_row["active"] is True
    assert str(session_row["source_artifact_id"]) == str(artifact["artifact_id"])
    assert session_row["metadata"] == {"congress": 130, "country": "us", "first": True, "second": True}


def test_congressional_stale_run_recovery_uses_typed_run_updates(
    catalog_database: None,
) -> None:
    """Only stale congressional ingestion runs are failed with explicit recovery evidence."""
    table = run_table()
    with session() as active_session:
        stale_id = active_session.execute(
            insert(table)
            .values(
                dataset_id="congress.govinfo_billstatus",
                mode="manual",
                status="running",
                parameters={},
                started_at=func.now() - text("interval '7 hours'"),
            )
            .returning(table.c.run_id)
        ).scalar_one()
        fresh_id = active_session.execute(
            insert(table)
            .values(
                dataset_id="congress.govinfo_billstatus",
                mode="manual",
                status="running",
                parameters={},
            )
            .returning(table.c.run_id)
        ).scalar_one()

    recovered = recover_stale_congressional_runs()
    with session() as active_session:
        states = {
            row["run_id"]: row["status"]
            for row in active_session.execute(
                select(table.c.run_id, table.c.status).where(table.c.run_id.in_((stale_id, fresh_id)))
            ).mappings()
        }

    assert stale_id in {row["run_id"] for row in recovered}
    assert states[stale_id] == "failed"
    assert states[fresh_id] == "running"


def test_legislation_artifact_registration_uses_typed_default_path(
    catalog_database: None,
) -> None:
    """Standalone legislative artifact registration keeps its merge-on-conflict contract."""
    registered = register_artifact(
        "congress.govinfo_billstatus",
        "https://example.test/billstatus.zip",
        "/tmp/billstatus.zip",
        "test-legislation-artifact",
        checksum_sha256="first-checksum",
        bytes_downloaded=10,
        period_start="2025-01-01",
        period_end="2025-12-31",
        metadata={"source": "first"},
    )
    updated = register_artifact(
        "congress.govinfo_billstatus",
        "https://example.test/billstatus-v2.zip",
        "/tmp/billstatus-v2.zip",
        "test-legislation-artifact",
        status="loaded",
        metadata={"loaded": True},
    )
    stored = get_artifact("congress.govinfo_billstatus", "test-legislation-artifact")

    assert registered["artifact_id"] == updated["artifact_id"]
    assert stored is not None
    assert stored["remote_url"] == "https://example.test/billstatus-v2.zip"
    assert stored["checksum_sha256"] == "first-checksum"
    assert stored["status"] == "loaded"
    assert stored["metadata"] == {"source": "first", "loaded": True}


def test_congressional_health_reads_canonical_evidence_with_sqlalchemy(
    catalog_database: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Health aggregation reads canonical tables without its former raw JSON query."""
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "data"))
    monkeypatch.setattr(
        congresshealth,
        "reconcile_openstates_votes",
        lambda congress: {"congress": congress, "source": {}, "canonical": {}, "duplicate_identifiers": []},
    )

    result = congresshealth.congressional_health()

    assert {"bills_118", "people", "roll_calls_119", "latest_runs"} <= set(result["canonical"])
    assert isinstance(result["canonical"]["latest_runs"], list)
    assert Path(result["report"]).is_file()


def test_fec_artifact_lookup_filters_and_orders_typed_metadata(
    catalog_database: None, tmp_path: Path
) -> None:
    """FEC staging receives only its requested family in deterministic cycle order."""
    source = tmp_path / "fec.zip"
    source.write_bytes(b"test fec artifact")
    for family, cycle in (("indiv", 2024), ("indiv", 2022), ("pas2", 2026)):
        register_local(
            ArtifactSpec(
                dataset_id="fec.campaign_finance",
                artifact_key=f"test-fec-{family}-{cycle}",
                url=f"https://example.test/{family}-{cycle}.zip",
                filename=f"{family}-{cycle}.zip",
                metadata={"family": family, "cycle": cycle},
            ),
            source,
        )

    artifacts = [
        artifact
        for artifact in fec_artifacts("indiv")
        if artifact["metadata"]["cycle"] in {2022, 2024}
    ]
    assert [artifact["metadata"]["cycle"] for artifact in artifacts] == [2022, 2024]


def test_pep_artifact_lookup_uses_typed_immutable_evidence(
    catalog_database: None, tmp_path: Path
) -> None:
    """PEP staging resolves registered CSV evidence through the shared mapping."""
    source = tmp_path / "pep.csv"
    source.write_text("SUMLEV,POP\n040,1\n")
    register_local(
        ArtifactSpec(
            dataset_id="census.population_estimates",
            artifact_key="test-pep-typed-artifact",
            url="https://example.test/pep.csv",
            filename="pep.csv",
        ),
        source,
    )

    artifact = pep_artifact("test-pep-typed-artifact")
    assert artifact["artifact_id"]
    assert artifact["local_path"] == str(source.resolve())


def test_dhc_artifact_lookup_uses_typed_immutable_evidence(
    catalog_database: None, tmp_path: Path
) -> None:
    """DHC loading resolves registered immutable archive evidence through the shared mapping."""
    source = tmp_path / "dhc.zip"
    source.write_bytes(b"test dhc artifact")
    register_local(
        ArtifactSpec(
            dataset_id="census.decennial",
            artifact_key="test-dhc-typed-artifact",
            url="https://example.test/dhc.zip",
            filename="dhc.zip",
        ),
        source,
    )

    artifact = dhc_artifact("test-dhc-typed-artifact")
    assert artifact["artifact_id"]
    assert artifact["local_path"] == str(source.resolve())


def test_cbp_artifact_lookup_uses_typed_immutable_evidence(
    catalog_database: None, tmp_path: Path
) -> None:
    """CBP staging resolves registered ZIP evidence through the shared mapping."""
    source = tmp_path / "cbp.zip"
    source.write_bytes(b"test cbp artifact")
    register_local(
        ArtifactSpec(
            dataset_id="census.business_patterns",
            artifact_key="test-cbp-typed-artifact",
            url="https://example.test/cbp.zip",
            filename="cbp.zip",
        ),
        source,
    )

    artifact = cbp_artifact("test-cbp-typed-artifact")
    assert artifact["artifact_id"]
    assert artifact["local_path"] == str(source.resolve())


def test_acs_artifact_lookup_scopes_typed_evidence_to_its_dataset(
    catalog_database: None, tmp_path: Path
) -> None:
    """ACS bulk loading cannot resolve an artifact from another dataset by key alone."""
    source = tmp_path / "acs.psv"
    source.write_text("GEO_ID|VALUE\n0400000US01|1\n")
    register_local(
        ArtifactSpec(
            dataset_id="census.acs_5_bulk",
            artifact_key="test-acs-typed-artifact",
            url="https://example.test/acs.psv",
            filename="acs.psv",
        ),
        source,
    )

    artifact = acs_artifact("census.acs_5_bulk", "test-acs-typed-artifact")
    assert artifact["artifact_id"]
    assert artifact["local_path"] == str(source.resolve())
    with pytest.raises(ValueError, match="has not been downloaded"):
        acs_artifact("census.tiger", "test-acs-typed-artifact")


def test_typed_postgis_boundary_mapping_round_trips_geometry(
    catalog_database: None,
) -> None:
    """GeoAlchemy maps canonical boundaries with their SRID and uniqueness intact."""
    geography = geography_table()
    boundary = geography_boundary_table()
    geography_statement = insert(geography).values(
        geography_type="test-spatial", geoid="001", name="Spatial test"
    )
    with session() as active_session:
        geography_id = active_session.execute(
            geography_statement.on_conflict_do_update(
                index_elements=(geography.c.geography_type, geography.c.geoid),
                set_={"name": geography_statement.excluded.name},
            ).returning(geography.c.geography_id)
        ).scalar_one()
        boundary_statement = insert(boundary).values(
            geography_id=geography_id,
            boundary_vintage=2030,
            geom=WKTElement("POINT(-77.0365 38.8977)", srid=4326),
        )
        active_session.execute(
            boundary_statement.on_conflict_do_update(
                index_elements=(boundary.c.geography_id, boundary.c.boundary_vintage),
                set_={"geom": boundary_statement.excluded.geom},
            )
        )

    with session() as active_session:
        srid, geometry = active_session.execute(
            select(func.ST_SRID(boundary.c.geom), func.ST_AsText(boundary.c.geom)).where(
                boundary.c.geography_id == geography_id, boundary.c.boundary_vintage == 2030
            )
        ).one()

    assert srid == 4326
    assert geometry == "POINT(-77.0365 38.8977)"


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


def test_census_health_reads_catalog_packages_through_sqlalchemy(
    catalog_database: None, tmp_path: Path
) -> None:
    """Census health reporting uses typed package and artifact reads."""
    original_data_root = settings.data_root
    settings.data_root = tmp_path / "data"
    try:
        assert sync_acs_bulk_packages() > 0
        report = census_health()
    finally:
        settings.data_root = original_data_root

    family = next(item for item in report["families"] if item["dataset_id"] == "census.acs_5_bulk")
    assert family["catalog_packages"] > 0
