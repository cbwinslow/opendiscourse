"""Comprehensive test suite for Story 1.7: Immutable Artifact Versions."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, connect, session
from opendiscourse_research.ingestion.bulk import ArtifactSpec, _upsert
from opendiscourse_research.models.catalog import artifact_table
from opendiscourse_research.models.core import document_table
from opendiscourse_research.repositories.legislation import (
    get_artifact,
    register_artifact,
)

_RUN_NS = uuid.uuid4().hex


def _scoped(suffix: str) -> str:
    """Namespace a test key or identifier to guarantee run isolation."""
    return f"{_RUN_NS}-{suffix}"


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


def test_initial_artifact_registration(catalog_database: None) -> None:
    """Initial registration creates version 1 with distinct UUID artifact_id."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-initial-v1")
    row = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/tiger-v1.zip",
        local_path="/tmp/tiger-v1.zip",
        artifact_key=artifact_key,
        checksum_sha256="checksum-alpha-1",
        bytes_downloaded=1024,
        status="downloaded",
        metadata={"cycle": 1},
    )

    assert row["artifact_id"] is not None
    assert row["artifact_version"] == 1
    assert row["checksum_sha256"] == "checksum-alpha-1"
    assert row["status"] == "downloaded"

    stored = get_artifact(dataset_id, artifact_key)
    assert stored is not None
    assert stored["artifact_id"] == row["artifact_id"]
    assert stored["artifact_version"] == 1
    assert stored["checksum_sha256"] == "checksum-alpha-1"


def test_unchanged_retry_same_checksum(catalog_database: None) -> None:
    """Unchanged retry with identical checksum performs idempotent update on current version."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-retry-same")
    v1 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/tiger-retry.zip",
        local_path="/tmp/tiger-retry.zip",
        artifact_key=artifact_key,
        checksum_sha256="checksum-bravo-1",
        status="downloaded",
        metadata={"attempt": 1},
    )

    retry = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/tiger-retry.zip",
        local_path="/tmp/tiger-retry.zip",
        artifact_key=artifact_key,
        checksum_sha256="checksum-bravo-1",
        status="loaded",
        metadata={"attempt": 2, "loaded": True},
    )

    assert retry["artifact_id"] == v1["artifact_id"]
    assert retry["artifact_version"] == 1
    assert retry["status"] == "loaded"

    # Verify only one version row exists
    table = artifact_table()
    with session() as active_session:
        count = active_session.execute(
            select(table.c.artifact_id).where(
                table.c.dataset_id == dataset_id,
                table.c.artifact_key == artifact_key,
            )
        ).all()
        assert len(count) == 1

    stored = get_artifact(dataset_id, artifact_key)
    assert stored is not None
    assert stored["artifact_id"] == v1["artifact_id"]
    assert stored["metadata"] == {"attempt": 2, "loaded": True}


def test_lifecycle_transition_planned_to_downloaded(catalog_database: None) -> None:
    """Initial row with null checksum transitions to downloaded without creating v2."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-planned-to-downloaded")
    initial = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/tiger-lifecycle.zip",
        local_path="/tmp/tiger-lifecycle.zip",
        artifact_key=artifact_key,
        status="planned",
        checksum_sha256=None,
    )

    assert initial["artifact_version"] == 1
    assert initial["checksum_sha256"] is None
    assert initial["status"] == "planned"

    updated = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/tiger-lifecycle.zip",
        local_path="/tmp/tiger-lifecycle.zip",
        artifact_key=artifact_key,
        status="downloaded",
        checksum_sha256="checksum-lifecycle-hash",
        bytes_downloaded=5000,
    )

    assert updated["artifact_id"] == initial["artifact_id"]
    assert updated["artifact_version"] == 1
    assert updated["status"] == "downloaded"
    assert updated["checksum_sha256"] == "checksum-lifecycle-hash"

    table = artifact_table()
    with session() as active_session:
        rows = active_session.execute(
            select(table.c.artifact_id).where(
                table.c.dataset_id == dataset_id,
                table.c.artifact_key == artifact_key,
            )
        ).all()
        assert len(rows) == 1


def test_changed_content_refresh_creates_new_version(catalog_database: None) -> None:
    """Registering a different checksum for the same key creates v2 while preserving v1."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-refresh-changed")

    v1 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/tiger-refresh.zip",
        local_path="/tmp/tiger-refresh-v1.zip",
        artifact_key=artifact_key,
        checksum_sha256="checksum-version-1",
        status="loaded",
    )
    assert v1["artifact_version"] == 1

    v2 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/tiger-refresh.zip",
        local_path="/tmp/tiger-refresh-v2.zip",
        artifact_key=artifact_key,
        checksum_sha256="checksum-version-2",
        status="downloaded",
    )

    assert v2["artifact_version"] == 2
    assert v2["artifact_id"] != v1["artifact_id"]
    assert v2["checksum_sha256"] == "checksum-version-2"

    # Historical v1 row is still preserved with original checksum
    v1_stored = get_artifact(dataset_id, artifact_key, version=1)
    assert v1_stored is not None
    assert v1_stored["artifact_id"] == v1["artifact_id"]
    assert v1_stored["checksum_sha256"] == "checksum-version-1"
    assert v1_stored["status"] == "loaded"

    # Default get_artifact returns latest v2
    latest = get_artifact(dataset_id, artifact_key)
    assert latest is not None
    assert latest["artifact_id"] == v2["artifact_id"]
    assert latest["artifact_version"] == 2
    assert latest["checksum_sha256"] == "checksum-version-2"


def test_historical_queryability_by_version(catalog_database: None) -> None:
    """Artifact versions are queryable by explicit version number or latest default."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-queryability")

    v1 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/q.zip",
        local_path="/tmp/q1.zip",
        artifact_key=artifact_key,
        checksum_sha256="q-hash-1",
    )
    v2 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/q.zip",
        local_path="/tmp/q2.zip",
        artifact_key=artifact_key,
        checksum_sha256="q-hash-2",
    )

    assert get_artifact(dataset_id, artifact_key, version=1)["artifact_id"] == v1["artifact_id"]
    assert get_artifact(dataset_id, artifact_key, version=2)["artifact_id"] == v2["artifact_id"]
    assert get_artifact(dataset_id, artifact_key)["artifact_id"] == v2["artifact_id"]
    assert get_artifact(dataset_id, artifact_key, version=999) is None


def test_existing_core_references_intact_and_repointer(catalog_database: None) -> None:
    """Core records reference v1, stay intact when v2 is created, and can re-point to v2."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-core-ref")

    v1 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/ref.zip",
        local_path="/tmp/ref1.zip",
        artifact_key=artifact_key,
        checksum_sha256="ref-hash-1",
    )

    documents = document_table()
    doc_source_key = _scoped("doc-test-versioning")

    with session() as active_session:
        doc_id = active_session.execute(
            insert(documents).values(
                document_type="bill_text",
                source_key=doc_source_key,
                artifact_id=v1["artifact_id"],
                language="en",
            ).returning(documents.c.document_id)
        ).scalar_one()

    # Register v2 with changed checksum
    v2 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/ref.zip",
        local_path="/tmp/ref2.zip",
        artifact_key=artifact_key,
        checksum_sha256="ref-hash-2",
    )
    assert v2["artifact_version"] == 2

    # Verify core.document still references v1
    with session() as active_session:
        doc = active_session.execute(
            select(documents.c.artifact_id).where(documents.c.document_id == doc_id)
        ).mappings().one()
        assert doc["artifact_id"] == v1["artifact_id"]

    # Re-pointer: loader processes v2 content and updates core.document
    with session() as active_session:
        active_session.execute(
            update(documents)
            .where(documents.c.document_id == doc_id)
            .values(artifact_id=v2["artifact_id"])
        )

    with session() as active_session:
        doc = active_session.execute(
            select(documents.c.artifact_id).where(documents.c.document_id == doc_id)
        ).mappings().one()
        assert doc["artifact_id"] == v2["artifact_id"]


def test_rollback_replay_creates_new_version(catalog_database: None) -> None:
    """Rolling back to an earlier checksum creates a new version, not a mutation."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-rollback-replay")

    v1 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/rb.zip",
        local_path="/tmp/rb1.zip",
        artifact_key=artifact_key,
        checksum_sha256="rb-hash-A",
    )
    v2 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/rb.zip",
        local_path="/tmp/rb2.zip",
        artifact_key=artifact_key,
        checksum_sha256="rb-hash-B",
    )
    assert v1["artifact_version"] == 1
    assert v2["artifact_version"] == 2

    # Upstream rolls back to rb-hash-A
    v3 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/rb.zip",
        local_path="/tmp/rb3.zip",
        artifact_key=artifact_key,
        checksum_sha256="rb-hash-A",
    )

    assert v3["artifact_version"] == 3
    assert v3["artifact_id"] not in (v1["artifact_id"], v2["artifact_id"])
    assert v3["checksum_sha256"] == "rb-hash-A"

    # All three versions are distinct and queryable
    stored_v1 = get_artifact(dataset_id, artifact_key, version=1)
    stored_v2 = get_artifact(dataset_id, artifact_key, version=2)
    stored_v3 = get_artifact(dataset_id, artifact_key, version=3)
    latest = get_artifact(dataset_id, artifact_key)

    assert stored_v1["checksum_sha256"] == "rb-hash-A"
    assert stored_v2["checksum_sha256"] == "rb-hash-B"
    assert stored_v3["checksum_sha256"] == "rb-hash-A"
    assert latest["artifact_id"] == v3["artifact_id"]
    assert latest["artifact_version"] == 3


def test_duplicate_explicit_version_violation(catalog_database: None) -> None:
    """Direct SQL insert with duplicate (dataset_id, artifact_key, artifact_version) fails."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-dup-version")
    table = artifact_table()

    with session() as active_session:
        active_session.execute(
            insert(table).values(
                dataset_id=dataset_id,
                artifact_key=artifact_key,
                artifact_version=1,
                remote_url="https://example.test/dup1.zip",
                local_path="/tmp/dup1.zip",
                status="planned",
            )
        )

    with (
        pytest.raises(IntegrityError, match="artifact_dataset_id_artifact_key_version_key"),
        session() as active_session,
    ):
        active_session.execute(
            insert(table).values(
                dataset_id=dataset_id,
                artifact_key=artifact_key,
                artifact_version=1,
                remote_url="https://example.test/dup2.zip",
                local_path="/tmp/dup2.zip",
                status="planned",
            )
        )


def test_raw_psycopg_conn_registration_and_query(catalog_database: None) -> None:
    """Raw psycopg connection executes versioned registration and query queries."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-raw-psycopg")

    with connect() as conn:
        v1 = register_artifact(
            dataset_id=dataset_id,
            remote_url="https://example.test/raw1.zip",
            local_path="/tmp/raw1.zip",
            artifact_key=artifact_key,
            checksum_sha256="raw-hash-1",
            conn=conn,
        )
        assert v1["artifact_version"] == 1
        assert v1["checksum_sha256"] == "raw-hash-1"

        # Retry with same checksum
        retry = register_artifact(
            dataset_id=dataset_id,
            remote_url="https://example.test/raw1.zip",
            local_path="/tmp/raw1.zip",
            artifact_key=artifact_key,
            checksum_sha256="raw-hash-1",
            status="loaded",
            conn=conn,
        )
        assert retry["artifact_id"] == v1["artifact_id"]
        assert retry["artifact_version"] == 1
        assert retry["status"] == "loaded"

        # New version with changed checksum
        v2 = register_artifact(
            dataset_id=dataset_id,
            remote_url="https://example.test/raw2.zip",
            local_path="/tmp/raw2.zip",
            artifact_key=artifact_key,
            checksum_sha256="raw-hash-2",
            conn=conn,
        )
        assert v2["artifact_version"] == 2
        assert v2["artifact_id"] != v1["artifact_id"]

        # Queries via conn
        stored_v1 = get_artifact(dataset_id, artifact_key, version=1, conn=conn)
        assert stored_v1 is not None
        assert stored_v1["artifact_id"] == v1["artifact_id"]

        stored_latest = get_artifact(dataset_id, artifact_key, conn=conn)
        assert stored_latest is not None
        assert stored_latest["artifact_id"] == v2["artifact_id"]
        assert stored_latest["artifact_version"] == 2


def test_bulk_upsert_version_aware(catalog_database: None, tmp_path: Path) -> None:
    """bulk._upsert handles initial registration, same-hash retry, and changed-hash versioning."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-bulk-upsert")
    path1 = tmp_path / "bulk1.zip"
    path1.write_bytes(b"content1")

    spec = ArtifactSpec(
        dataset_id=dataset_id,
        artifact_key=artifact_key,
        url="https://example.test/bulk.zip",
        filename="bulk.zip",
    )

    # 1. downloading status (checksum None)
    _upsert(spec, path1, "downloading")
    stored = get_artifact(dataset_id, artifact_key)
    assert stored is not None
    assert stored["artifact_version"] == 1
    assert stored["status"] == "downloading"
    assert stored["checksum_sha256"] is None

    # 2. downloaded transition with hash1
    _upsert(spec, path1, "downloaded", bytes=100, checksum="bulk-hash-1")
    stored = get_artifact(dataset_id, artifact_key)
    assert stored is not None
    assert stored["artifact_version"] == 1
    assert stored["status"] == "downloaded"
    assert stored["checksum_sha256"] == "bulk-hash-1"

    # 3. retry same hash (e.g. skipped)
    _upsert(spec, path1, "skipped", bytes=100, checksum="bulk-hash-1")
    stored = get_artifact(dataset_id, artifact_key)
    assert stored is not None
    assert stored["artifact_version"] == 1
    assert stored["status"] == "skipped"

    # 4. new download with changed hash creates version 2
    path2 = tmp_path / "bulk2.zip"
    path2.write_bytes(b"content2")
    _upsert(spec, path2, "downloaded", bytes=200, checksum="bulk-hash-2")

    stored_v1 = get_artifact(dataset_id, artifact_key, version=1)
    stored_v2 = get_artifact(dataset_id, artifact_key, version=2)
    stored_latest = get_artifact(dataset_id, artifact_key)

    assert stored_v1 is not None
    assert stored_v1["artifact_version"] == 1
    assert stored_v1["checksum_sha256"] == "bulk-hash-1"

    assert stored_v2 is not None
    assert stored_v2["artifact_version"] == 2
    assert stored_v2["checksum_sha256"] == "bulk-hash-2"

    assert stored_latest is not None
    assert stored_latest["artifact_version"] == 2
    assert stored_latest["artifact_id"] == stored_v2["artifact_id"]


def test_loaders_resolve_newest_version(catalog_database: None) -> None:
    """Loaders (acs, cbp, dhc, pep, tiger) resolve newest v2 when multiple versions exist."""
    from opendiscourse_research.ingestion.acs_load import _artifact as acs_artifact
    from opendiscourse_research.ingestion.cbp_load import _artifact as cbp_artifact
    from opendiscourse_research.ingestion.dhc_load import _artifact as dhc_artifact
    from opendiscourse_research.ingestion.pep_load import _artifact as pep_artifact
    from opendiscourse_research.ingestion.tiger_load import _artifact as tiger_artifact

    loaders = [
        ("census.acs_5", _scoped("acs-multi-ver"), lambda k: acs_artifact("census.acs_5", k)),
        ("census.business_patterns", _scoped("cbp-multi-ver"), cbp_artifact),
        ("census.decennial", _scoped("dhc-multi-ver"), dhc_artifact),
        ("census.population_estimates", _scoped("pep-multi-ver"), pep_artifact),
        ("census.tiger", _scoped("tiger-multi-ver"), tiger_artifact),
    ]

    for dataset_id, key, loader_fn in loaders:
        v1 = register_artifact(
            dataset_id=dataset_id,
            remote_url=f"https://example.test/{key}-v1.zip",
            local_path=f"/tmp/{key}-v1.zip",
            artifact_key=key,
            checksum_sha256=f"hash-{key}-v1",
            status="downloaded",
        )
        v2 = register_artifact(
            dataset_id=dataset_id,
            remote_url=f"https://example.test/{key}-v2.zip",
            local_path=f"/tmp/{key}-v2.zip",
            artifact_key=key,
            checksum_sha256=f"hash-{key}-v2",
            status="downloaded",
        )
        assert v1["artifact_version"] == 1
        assert v2["artifact_version"] == 2

        resolved = loader_fn(key)
        assert resolved["artifact_id"] == v2["artifact_id"]
        assert resolved["local_path"] == f"/tmp/{key}-v2.zip"


def test_completed_artifact_not_mutated_by_predownload(catalog_database: None, tmp_path: Path) -> None:
    """Pre-download unchecksummed calls (downloading/planned/failed) do not mutate completed artifacts."""
    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-immutable-guard")

    # 1. SQLAlchemy register_artifact guard
    v1 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/guard.zip",
        local_path="/tmp/guard.zip",
        artifact_key=artifact_key,
        checksum_sha256="guard-hash-1",
        status="downloaded",
    )
    assert v1["status"] == "downloaded"

    for bad_status in ("downloading", "failed", "planned"):
        result = register_artifact(
            dataset_id=dataset_id,
            remote_url="https://example.test/guard.zip",
            local_path="/tmp/guard-attempt.zip",
            artifact_key=artifact_key,
            checksum_sha256=None,
            status=bad_status,
        )
        assert result["status"] == "downloaded"
        assert result["checksum_sha256"] == "guard-hash-1"
        assert result["local_path"] == "/tmp/guard.zip"

    # Verify DB record is untouched
    stored = get_artifact(dataset_id, artifact_key)
    assert stored["status"] == "downloaded"
    assert stored["checksum_sha256"] == "guard-hash-1"
    assert stored["local_path"] == "/tmp/guard.zip"

    # 2. Raw psycopg register_artifact guard
    with connect() as conn:
        for bad_status in ("downloading", "failed", "planned"):
            result_raw = register_artifact(
                dataset_id=dataset_id,
                remote_url="https://example.test/guard.zip",
                local_path="/tmp/guard-attempt-raw.zip",
                artifact_key=artifact_key,
                checksum_sha256=None,
                status=bad_status,
                conn=conn,
            )
            assert result_raw["status"] == "downloaded"
            assert result_raw["checksum_sha256"] == "guard-hash-1"

    # 3. bulk._upsert guard
    bulk_key = _scoped("tiger-bulk-guard")
    bulk_path = tmp_path / "bulk_guard.zip"
    bulk_path.write_bytes(b"guard content")
    spec = ArtifactSpec(
        dataset_id=dataset_id,
        artifact_key=bulk_key,
        url="https://example.test/bulk_guard.zip",
        filename="bulk_guard.zip",
    )
    _upsert(spec, bulk_path, "downloaded", bytes=50, checksum="bulk-guard-hash")

    stored_bulk = get_artifact(dataset_id, bulk_key)
    assert stored_bulk["status"] == "downloaded"
    assert stored_bulk["checksum_sha256"] == "bulk-guard-hash"

    # Attempt pre-download / failed calls without checksum
    _upsert(spec, bulk_path, "downloading")
    stored_bulk2 = get_artifact(dataset_id, bulk_key)
    assert stored_bulk2["status"] == "downloaded"

    _upsert(spec, bulk_path, "failed", error="HTTP 500 error")
    stored_bulk3 = get_artifact(dataset_id, bulk_key)
    assert stored_bulk3["status"] == "downloaded"
    table = artifact_table()
    with session() as active_session:
        err_msg = active_session.execute(
            select(table.c.error_message).where(
                table.c.dataset_id == dataset_id,
                table.c.artifact_key == bulk_key,
            )
        ).scalar_one()
        assert err_msg is None


def test_downgrade_prunes_older_versions(catalog_database: None) -> None:
    """Alembic downgrade from c5e2d1a4f783 prunes non-latest versions before re-creating constraint."""
    from alembic import command
    from alembic.config import Config

    dataset_id = "census.tiger"
    artifact_key = _scoped("tiger-downgrade-prune")

    v1 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/prune1.zip",
        local_path="/tmp/prune1.zip",
        artifact_key=artifact_key,
        checksum_sha256="prune-hash-1",
    )
    v2 = register_artifact(
        dataset_id=dataset_id,
        remote_url="https://example.test/prune2.zip",
        local_path="/tmp/prune2.zip",
        artifact_key=artifact_key,
        checksum_sha256="prune-hash-2",
    )
    assert v1["artifact_version"] == 1
    assert v2["artifact_version"] == 2

    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", settings.database_url)

    # Downgrade to b1e5c8a3d942 (prior revision)
    command.downgrade(config, "b1e5c8a3d942")

    # Verify that in b1e5c8a3d942, v1 was pruned and v2 was kept
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT artifact_id, checksum_sha256 FROM ingest.artifact WHERE dataset_id = %s AND artifact_key = %s",
            (dataset_id, artifact_key),
        )
        rows = cur.fetchall()
        assert len(rows) == 1
        assert str(rows[0]["artifact_id"]) == str(v2["artifact_id"])
        assert rows[0]["checksum_sha256"] == "prune-hash-2"

    # Re-upgrade to head
    command.upgrade(config, "head")

