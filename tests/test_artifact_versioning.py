"""Serial database coverage for immutable artifact evidence versions."""

from __future__ import annotations

import os
import json
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select
from sqlalchemy.engine import make_url

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, connect, session
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion import bulk
from opendiscourse_research.artifact_storage import retain_artifact_bytes
from opendiscourse_research.models.catalog import artifact_table, CatalogSnapshot
from opendiscourse_research.models.core import document_table
from opendiscourse_research.repositories.legislation import (
    get_artifact,
    register_artifact,
)

_NAMESPACE = uuid.uuid4().hex
pytestmark = pytest.mark.db


def _key(name: str) -> str:
    """Return a test-isolated logical artifact key."""
    return f"story-1-7-{_NAMESPACE}-{name}"


def _psycopg_url(url: str) -> str:
    """Translate the testcontainers SQLAlchemy URL to a psycopg URL."""
    return url.replace("postgresql+psycopg2://", "postgresql://", 1)


@pytest.fixture(scope="module")
def catalog_database() -> None:
    """Migrate either the configured test DB or an isolated PostGIS container."""
    original_url = settings.database_url
    external_url = os.environ.get("OPENDISCOURSE_TEST_DATABASE_URL")
    if external_url:
        # Artifact history is permanent by design and blocks the migration downgrade
        # that other test modules perform, so never share their database.
        private = f"od_artifacts_{uuid.uuid4().hex[:12]}"
        with psycopg.connect(external_url, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{private}"')
        settings.database_url = (
            make_url(external_url)
            .set(database=private)
            .render_as_string(hide_password=False)
        )
        _engine.cache_clear()
        apply_migrations()
        sync_inventory()
        try:
            yield
        finally:
            settings.database_url = original_url
            _engine.cache_clear()
            with psycopg.connect(external_url, autocommit=True) as admin:
                admin.execute(f'DROP DATABASE IF EXISTS "{private}" WITH (FORCE)')
        return

    postgres = pytest.importorskip("testcontainers.postgres")
    with postgres.PostgresContainer(
        "postgis/postgis:17-3.5", username="test", password="test", dbname="test"
    ) as container:
        settings.database_url = _psycopg_url(container.get_connection_url())
        apply_migrations()
        sync_inventory()
        try:
            yield
        finally:
            settings.database_url = original_url
            _engine.cache_clear()


def _register(key: str, checksum: str | None, *, conn: object | None = None) -> dict:
    """Register a virtual source; virtual records intentionally have no local bytes."""
    return register_artifact(
        "census.tiger",
        "https://example.test/source.zip",
        f"virtual://{key}/{checksum or 'attempt'}",
        key,
        checksum_sha256=checksum,
        status="downloaded" if checksum else "failed",
        conn=conn,
    )


def test_versions_preserve_referenced_v1_and_a_to_b_to_a(
    catalog_database: None, tmp_path, monkeypatch
) -> None:
    """Changed bytes append versions without changing foreign-key historical evidence."""
    key = _key("historical")
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake"))
    source = tmp_path / "source.zip"
    spec = ArtifactSpec(
        "census.tiger", key, "https://example.test/bytes", "historical.zip"
    )

    def admit(body):
        source.write_bytes(body)
        register_local(spec, source)
        return get_artifact(spec.dataset_id, key)

    v1 = admit(b"checksum-a")
    retry = admit(b"checksum-a")
    assert retry["artifact_id"] == v1["artifact_id"]
    with session() as active_session:
        document_id = active_session.execute(
            insert(document_table())
            .values(
                document_type="bill_text",
                source_key=_key("document"),
                artifact_id=v1["artifact_id"],
                language="en",
            )
            .returning(document_table().c.document_id)
        ).scalar_one()
    v2 = admit(b"checksum-b")
    v3 = admit(b"checksum-a")
    assert [v1["artifact_version"], v2["artifact_version"], v3["artifact_version"]] == [
        1,
        2,
        3,
    ]
    historical = get_artifact("census.tiger", key, version=1)
    assert historical["checksum_sha256"] == sha256(b"checksum-a").hexdigest()
    assert Path(historical["local_path"]).read_bytes() == b"checksum-a"
    assert historical["artifact_version"] == 1
    assert get_artifact("census.tiger", key)["artifact_id"] == v3["artifact_id"]
    with session() as active_session:
        assert (
            active_session.execute(
                select(document_table().c.artifact_id).where(
                    document_table().c.document_id == document_id
                )
            ).scalar_one()
            == v1["artifact_id"]
        )


@pytest.mark.parametrize("raw", [False, True])
def test_failed_provisional_attempt_promotes_without_changing_completed(
    catalog_database: None, raw
) -> None:
    """A failed refresh is provisional and a verified retry promotes that attempt only."""
    key = _key(f"provisional-{raw}")
    with connect() as conn:
        supplied = conn if raw else None
        v1 = _register(key, "checksum-v1", conn=supplied)
        failed = _register(key, None, conn=supplied)
        promoted = _register(key, "checksum-v2", conn=supplied)
    assert failed["artifact_version"] == 2
    assert promoted["artifact_id"] == failed["artifact_id"]
    assert promoted["artifact_version"] == 2
    assert (
        get_artifact("census.tiger", key, version=1)["artifact_id"] == v1["artifact_id"]
    )
    assert (
        get_artifact("census.tiger", key, version=1)["checksum_sha256"] == "checksum-v1"
    )


def test_virtual_sources_and_legacy_positional_lookup_remain_compatible(
    catalog_database: None,
) -> None:
    """No-byte references remain valid and the third positional argument is a connection."""
    key = _key("virtual")
    with connect() as conn:
        artifact = register_artifact(
            "openstates.legislation",
            "openstates_source://opencivicdata_voteevent",
            "openstates_source.opencivicdata_voteevent",
            key,
            status="loaded",
            conn=conn,
        )
        assert artifact["checksum_sha256"] is None
        assert (
            get_artifact("openstates.legislation", key, conn)["artifact_id"]
            == artifact["artifact_id"]
        )


def test_real_bytes_must_be_checksum_retained_and_bulk_retains_versions(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Completed byte artifacts are accepted only after checksum-addressed retention."""
    source = tmp_path / "source.zip"
    source.write_bytes(b"first bytes")
    checksum = sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="checksum-specific"):
        register_artifact(
            "census.tiger",
            "https://example.test/a",
            str(source),
            _key("reject"),
            checksum_sha256=checksum,
        )

    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake"))
    spec = ArtifactSpec(
        "census.tiger", _key("bulk"), "https://example.test/a", "artifact.zip"
    )
    retained_v1 = register_local(spec, source)
    assert checksum in retained_v1.name
    source.write_bytes(b"second bytes")
    retained_v2 = register_local(spec, source)
    row_v1 = get_artifact("census.tiger", spec.artifact_key, version=1)
    row_v2 = get_artifact("census.tiger", spec.artifact_key, version=2)
    assert retained_v1.read_bytes() == b"first bytes"
    assert retained_v2.read_bytes() == b"second bytes"
    assert row_v1["local_path"] == str(retained_v1)
    assert row_v2["local_path"] == str(retained_v2)


def test_raw_lookup_and_raw_autocommit_concurrency(catalog_database: None) -> None:
    """Raw callers retrieve exact history and serialize initial v1 allocation."""
    key = _key("raw")
    with connect() as conn:
        v1 = _register(key, "raw-a", conn=conn)
        v2 = _register(key, "raw-b", conn=conn)
        assert (
            get_artifact("census.tiger", key, conn, version=1)["artifact_id"]
            == v1["artifact_id"]
        )
        assert (
            get_artifact("census.tiger", key, conn, version=2)["artifact_id"]
            == v2["artifact_id"]
        )

    concurrent_key = _key("raw-concurrent")

    def register() -> dict:
        with connect() as conn:
            conn.autocommit = True
            return _register(concurrent_key, "concurrent-a", conn=conn)

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda _: register(), range(2)))
    assert rows[0]["artifact_id"] == rows[1]["artifact_id"]
    assert rows[0]["artifact_version"] == rows[1]["artifact_version"] == 1


def test_loaders_and_acs_snapshot_select_latest_version(catalog_database: None) -> None:
    """Every bulk consumer deliberately resolves v2 rather than an arbitrary row."""
    from opendiscourse_research.ingestion.acs_load import _artifact as acs_artifact
    from opendiscourse_research.ingestion.cbp_load import _artifact as cbp_artifact
    from opendiscourse_research.ingestion.dhc_load import _artifact as dhc_artifact
    from opendiscourse_research.ingestion.pep_load import _artifact as pep_artifact
    from opendiscourse_research.ingestion.tiger_load import _artifact as tiger_artifact

    consumers = [
        ("census.acs_5", lambda key: acs_artifact("census.acs_5", key)),
        ("census.business_patterns", cbp_artifact),
        ("census.decennial", dhc_artifact),
        ("census.population_estimates", pep_artifact),
        ("census.tiger", tiger_artifact),
    ]
    for dataset_id, consumer in consumers:
        key = _key(dataset_id.rsplit(".", 1)[-1])
        v1 = register_artifact(
            dataset_id,
            "https://example.test/v1",
            f"virtual://{key}/1",
            key,
            checksum_sha256="v1",
            status="downloaded",
        )
        v2 = register_artifact(
            dataset_id,
            "https://example.test/v2",
            f"virtual://{key}/2",
            key,
            checksum_sha256="v2",
            status="downloaded",
        )
        assert consumer(key)["artifact_id"] == v2["artifact_id"] != v1["artifact_id"]


def test_downgrade_refuses_artifact_history(catalog_database: None) -> None:
    """Downgrade fails closed and leaves multiple immutable evidence rows intact."""
    key = _key("downgrade")
    _register(key, "old")
    _register(key, "new")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    with pytest.raises(Exception, match="cannot downgrade immutable artifact versions"):
        command.downgrade(config, "b1e5c8a3d942")
    assert get_artifact("census.tiger", key, version=1) is not None
    assert get_artifact("census.tiger", key, version=2) is not None


@pytest.mark.parametrize("raw", [False, True])
def test_admission_and_legacy_repair(catalog_database, tmp_path, raw):
    """Missing evidence fails; verified refresh appends after a matching legacy row."""
    key = _key(f"legacy-{raw}")
    source = tmp_path / "legacy.zip"
    source.write_bytes(b"legacy bytes")
    checksum = sha256(source.read_bytes()).hexdigest()
    with session() as active:
        legacy_id = active.execute(
            insert(artifact_table())
            .values(
                dataset_id="census.tiger",
                artifact_key=key,
                remote_url="https://example.test/legacy",
                local_path=str(source),
                checksum_sha256=checksum,
                status="loaded",
            )
            .returning(artifact_table().c.artifact_id)
        ).scalar_one()
    retained = retain_artifact_bytes(source, checksum)
    with connect() as conn:
        supplied = conn if raw else None
        for invalid in (
            tmp_path / "missing.zip",
            tmp_path / f"missing.{checksum}.zip",
            tmp_path,
        ):
            with pytest.raises(ValueError, match="checksum-specific"):
                register_artifact(
                    "census.tiger",
                    "https://example.test/a",
                    str(invalid),
                    key,
                    checksum_sha256=checksum,
                    conn=supplied,
                )
        repaired = register_artifact(
            "census.tiger",
            "https://example.test/a",
            str(retained),
            key,
            checksum_sha256=checksum,
            conn=supplied,
        )
        assert repaired["artifact_version"] == 2
        assert repaired["artifact_id"] != legacy_id
        old = get_artifact("census.tiger", key, supplied, version=1)
        assert old["local_path"] == str(source)
        assert old["status"] == "loaded"
        retry = register_artifact(
            "census.tiger",
            "https://example.test/a",
            str(retained),
            key,
            checksum_sha256=checksum,
            conn=supplied,
        )
        assert retry["artifact_id"] == repaired["artifact_id"]


@pytest.mark.parametrize("raw", [False, True])
def test_completed_checksumless_records_never_promote(catalog_database, raw):
    key = _key(f"completed-reference-{raw}")
    with connect() as conn:
        supplied = conn if raw else None
        completed = register_artifact(
            "census.tiger",
            "virtual://reference",
            "virtual://reference",
            key,
            status="loaded",
            conn=supplied,
        )
        verified = _register(key, "verified-new", conn=supplied)
        assert verified["artifact_version"] == 2
        old = get_artifact("census.tiger", key, supplied, version=1)
        assert old["artifact_id"] == completed["artifact_id"]
        assert old["checksum_sha256"] is None
        assert old["status"] == "loaded"


@pytest.mark.parametrize(
    "routes",
    [
        ("session", "session"),
        ("transaction", "transaction"),
        ("autocommit", "autocommit"),
        ("session", "transaction"),
        ("session", "autocommit"),
    ],
)
def test_registration_routes_serialize(catalog_database, routes):
    """Overlapping initial registration shares one version across all entry points."""
    key = _key("-".join(routes))
    barrier = threading.Barrier(2)

    def register(route):
        if route == "session":
            barrier.wait(timeout=10)
            return _register(key, "same-content")
        with connect() as conn:
            conn.autocommit = route == "autocommit"
            if not conn.autocommit:
                conn.execute("SELECT 1")  # already inside a caller-owned transaction
            barrier.wait(timeout=10)
            return _register(key, "same-content", conn=conn)

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(register, routes))
    assert rows[0]["artifact_id"] == rows[1]["artifact_id"]
    assert rows[0]["artifact_version"] == rows[1]["artifact_version"] == 1
    assert get_artifact("census.tiger", key, version=2) is None


@pytest.mark.parametrize("already_active", [False, True])
def test_raw_registration_preserves_caller_rollback(catalog_database, already_active):
    key = _key(f"rollback-{already_active}")
    with connect() as conn:
        if already_active:
            conn.execute("SELECT 1")
        _register(key, "rolled-back", conn=conn)
        conn.rollback()
    assert get_artifact("census.tiger", key) is None


@contextmanager
def _download_server():
    """Serve real streams including a truncated response and HTTP range resumes."""
    state = {
        "body": b"first complete bytes",
        "fail": False,
        "ignore_range": False,
        "requests": [],
        "active": 0,
        "max_active": 0,
    }
    mutex = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            with mutex:
                state["requests"].append(self.headers.get("Range"))
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            try:
                time.sleep(0.03)
                offset = int(
                    self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0]
                )
                if state["ignore_range"]:
                    offset = 0
                body = state["body"][offset:]
                self.send_response(206 if offset else 200)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", "application/zip")
                if offset:
                    self.send_header(
                        "Content-Range",
                        f"bytes {offset}-{len(state['body']) - 1}/{len(state['body'])}",
                    )
                self.end_headers()
                if state["fail"]:
                    self.wfile.write(body[:6])
                    self.wfile.flush()
                    self.connection.shutdown(socket.SHUT_RDWR)
                else:
                    self.wfile.write(body)
            finally:
                with mutex:
                    state["active"] -= 1

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/file.zip", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_download_concurrency_cache_and_same_byte_refresh(
    catalog_database, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    monkeypatch.setattr(bulk, "client", lambda: httpx.Client(trust_env=False))
    with _download_server() as (url, state):
        spec = ArtifactSpec("census.tiger", _key("http-concurrent"), url, "remote.zip")
        barrier = threading.Barrier(2)

        def acquire(_):
            barrier.wait(timeout=10)
            return bulk.download(spec, overwrite=True, chunk_size=3)

        with ThreadPoolExecutor(max_workers=2) as pool:
            paths = list(pool.map(acquire, range(2)))
        assert paths[0] == paths[1]
        assert paths[0].read_bytes() == state["body"]
        assert len(state["requests"]) == 2
        assert state["max_active"] == 1
        assert bulk.download(spec) == paths[0]
        assert len(state["requests"]) == 2  # cache never issues another request
        assert get_artifact(spec.dataset_id, spec.artifact_key)["artifact_version"] == 1
        state["body"] = b"changed remote bytes"
        newer = bulk.download(spec, overwrite=True)
        assert newer != paths[0]
        assert paths[0].read_bytes() == b"first complete bytes"
        assert get_artifact(spec.dataset_id, spec.artifact_key)["artifact_version"] == 2


@pytest.mark.parametrize("ignore_range", [False, True])
def test_download_failure_resume_and_provisional_promotion(
    catalog_database, tmp_path, monkeypatch, ignore_range
):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    monkeypatch.setattr(bulk, "client", lambda: httpx.Client(trust_env=False))
    with _download_server() as (url, state):
        spec = ArtifactSpec(
            "census.tiger", _key(f"http-failure-{ignore_range}"), url, "remote.zip"
        )
        original_path = bulk.download(spec, chunk_size=3)
        original = get_artifact(spec.dataset_id, spec.artifact_key)
        state.update(body=b"a changed response for retry", fail=True)
        with pytest.raises(httpx.RemoteProtocolError):
            bulk.download(spec, overwrite=True, chunk_size=3)
        failed = get_artifact(spec.dataset_id, spec.artifact_key)
        assert failed["status"] == "failed"
        assert failed["artifact_version"] == 2
        assert failed["checksum_sha256"] is None
        partial = bulk.artifact_path(spec).with_suffix(".zip.part")
        assert partial.read_bytes() == state["body"][:6]
        state.update(fail=False, ignore_range=ignore_range)
        completed_path = bulk.download(spec, chunk_size=3)
        completed = get_artifact(spec.dataset_id, spec.artifact_key)
        assert state["requests"][-1] == "bytes=6-"
        assert completed["artifact_id"] == failed["artifact_id"]
        assert completed["checksum_sha256"] == sha256(state["body"]).hexdigest()
        assert completed_path.read_bytes() == state["body"]
        assert not partial.exists()
        assert original_path.read_bytes() == b"first complete bytes"
        assert get_artifact(spec.dataset_id, spec.artifact_key, version=1) == original


def test_acs_sync_snapshots_reference_each_retained_version(
    catalog_database, tmp_path, monkeypatch
):
    from opendiscourse_research import browser

    year = 1900  # test-only manifest year, no provider calls
    manifest = tmp_path / "tables.json"
    monkeypatch.setattr(browser, "_acs_manifest", lambda _: manifest)
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake"))
    spec = ArtifactSpec(
        "census.acs_5", f"tables-{year}", "https://example.test/tables", "tables.json"
    )
    versions = []
    for title in ("First catalog", "Updated catalog"):
        manifest.write_text(
            json.dumps({"tables": [{"id": _key("acs-table"), "title": title}]})
        )
        register_local(spec, manifest)
        version = get_artifact(spec.dataset_id, spec.artifact_key)
        versions.append(version)
        assert browser.sync_acs(year) == 1
        with session() as active:
            snapshot = (
                active.execute(
                    select(CatalogSnapshot.__table__).where(
                        CatalogSnapshot.checksum_sha256 == version["checksum_sha256"]
                    )
                )
                .mappings()
                .one()
            )
        assert snapshot["artifact_id"] == version["artifact_id"]
    assert versions[0]["artifact_id"] != versions[1]["artifact_id"]
    with session() as active:
        snapshots = (
            active.execute(
                select(CatalogSnapshot.__table__).where(
                    CatalogSnapshot.artifact_id.in_(
                        [row["artifact_id"] for row in versions]
                    )
                )
            )
            .mappings()
            .all()
        )
    assert len(snapshots) == 2


def test_download_adopts_legacy_cache_without_removing_original(
    catalog_database, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    spec = ArtifactSpec(
        "census.tiger",
        _key("legacy-cache"),
        "https://example.test/archive",
        "legacy.zip",
    )
    legacy_path = bulk.artifact_path(spec)
    legacy_path.write_bytes(b"legacy cached evidence")
    checksum = sha256(legacy_path.read_bytes()).hexdigest()
    with session() as active:
        active.execute(
            insert(artifact_table()).values(
                dataset_id=spec.dataset_id,
                artifact_key=spec.artifact_key,
                remote_url=spec.url,
                local_path=str(legacy_path),
                checksum_sha256=checksum,
                status="loaded",
            )
        )
    retained = bulk.download(spec)
    assert retained != legacy_path
    assert (
        retained.read_bytes() == legacy_path.read_bytes() == b"legacy cached evidence"
    )
    assert get_artifact(spec.dataset_id, spec.artifact_key)["artifact_version"] == 2
    old = get_artifact(spec.dataset_id, spec.artifact_key, version=1)
    assert old["local_path"] == str(legacy_path)
    assert old["status"] == "loaded"


@pytest.mark.parametrize("raw", [False, True])
def test_real_admission_supersedes_matching_virtual_reference(catalog_database, tmp_path, raw):
    key = _key(f"virtual-to-bytes-{raw}")
    source = tmp_path / "bytes.zip"
    source.write_bytes(b"actual retained bytes")
    checksum = sha256(source.read_bytes()).hexdigest()
    retained = retain_artifact_bytes(source, checksum)
    with connect() as conn:
        supplied = conn if raw else None
        virtual = _register(key, checksum, conn=supplied)
        real = register_artifact("census.tiger", "https://example.test/source", str(retained), key,
                                 checksum_sha256=checksum, conn=supplied)
        assert real["artifact_id"] != virtual["artifact_id"]
        assert real["artifact_version"] == 2
        assert real["local_path"] == str(retained)
        assert get_artifact("census.tiger", key, supplied, version=1)["local_path"].startswith("virtual://")


def _artifact_row(artifact_id) -> dict:
    """Read one full artifact row, including columns registration does not return."""
    table = artifact_table()
    with session() as active_session:
        return dict(
            active_session.execute(
                select(table).where(table.c.artifact_id == artifact_id)
            )
            .mappings()
            .one()
        )


def _bulk_consumers():
    """Every loader that resolves an artifact by key, with its dataset."""
    from opendiscourse_research.ingestion.acs_load import _artifact as acs_artifact
    from opendiscourse_research.ingestion.cbp_load import _artifact as cbp_artifact
    from opendiscourse_research.ingestion.dhc_load import _artifact as dhc_artifact
    from opendiscourse_research.ingestion.pep_load import _artifact as pep_artifact
    from opendiscourse_research.ingestion.tiger_load import _artifact as tiger_artifact

    return [
        ("census.acs_5", lambda key: acs_artifact("census.acs_5", key)),
        ("census.business_patterns", cbp_artifact),
        ("census.decennial", dhc_artifact),
        ("census.population_estimates", pep_artifact),
        ("census.tiger", tiger_artifact),
    ]


def test_failed_refresh_never_hides_current_version_from_any_consumer(
    catalog_database: None,
) -> None:
    """Story 1.7 review: a failed v2 must not shadow verified v1 for loaders/health."""
    from opendiscourse_research.censushealth import _artifacts as health_artifacts
    from opendiscourse_research.repositories.artifacts import get_current_artifact

    for dataset_id, consumer in _bulk_consumers():
        key = _key(f"shadow-{dataset_id.rsplit('.', 1)[-1]}")
        v1 = register_artifact(
            dataset_id,
            "https://example.test/v1",
            f"virtual://{key}/1",
            key,
            checksum_sha256="v1",
            status="downloaded",
        )
        failed = register_artifact(
            dataset_id,
            "https://example.test/v2",
            f"virtual://{key}/attempt",
            key,
            status="failed",
            error_message="HTTP 503",
        )
        assert (failed["artifact_version"], failed["status"]) == (2, "failed")
        assert consumer(key)["artifact_id"] == v1["artifact_id"]
        current = get_current_artifact(key, dataset_id=dataset_id)
        assert current["artifact_id"] == v1["artifact_id"]
        health = health_artifacts([key])
        assert [row["artifact_id"] for row in health] == [v1["artifact_id"]]


def test_health_reports_only_failed_attempts_as_failed_not_missing(
    catalog_database: None,
) -> None:
    from opendiscourse_research.censushealth import _artifacts as health_artifacts
    from opendiscourse_research.ingestion.tiger_load import _artifact as tiger_artifact
    from opendiscourse_research.repositories.artifacts import get_current_artifact

    key = _key("only-failed")
    register_artifact(
        "census.tiger",
        "https://example.test/x",
        f"virtual://{key}/attempt",
        key,
        status="failed",
        error_message="HTTP 503",
    )
    rows = health_artifacts([key])
    assert [(row["status"], row["error_message"]) for row in rows] == [
        ("failed", "HTTP 503")
    ]
    assert get_current_artifact(key) is None
    with pytest.raises(ValueError, match="has not been downloaded"):
        tiger_artifact(key)


def test_fec_staging_reads_only_the_current_version_of_each_cycle(
    catalog_database: None,
) -> None:
    """A changed cycle file must not be staged twice (v1 and v2 rows)."""
    from opendiscourse_research.ingestion import fec_bulk

    family = f"t{_NAMESPACE[:8]}"
    ids = {}
    for cycle, checksums in ((2022, ["a"]), (2024, ["b1", "b2"])):
        key = _key(f"fec-{cycle}")
        for checksum in checksums:
            ids[cycle] = register_artifact(
                fec_bulk.DATASET_ID,
                f"https://example.test/{cycle}",
                f"virtual://{key}/{checksum}",
                key,
                checksum_sha256=checksum,
                status="downloaded",
                metadata={"family": family, "cycle": cycle},
            )["artifact_id"]
    register_artifact(  # a later failed refresh of 2024 must not hide 2024 v2
        fec_bulk.DATASET_ID,
        "https://example.test/2024",
        f"virtual://{_key('fec-2024')}/attempt",
        _key("fec-2024"),
        status="failed",
        metadata={"family": family, "cycle": 2024},
    )
    staged = fec_bulk._registered_artifacts(family)
    assert [row["artifact_id"] for row in staged] == [ids[2022], ids[2024]]


def test_current_artifact_view_matches_repository_statuses(
    catalog_database: None,
) -> None:
    from opendiscourse_research.repositories.artifacts import CURRENT_STATUSES

    with connect() as conn:
        definition = conn.execute(
            "SELECT pg_get_viewdef('ingest.current_artifact'::regclass) AS definition"
        ).fetchone()["definition"]
    for status in CURRENT_STATUSES:
        assert f"'{status}'" in definition
    for status in ("failed", "planned", "downloading"):
        assert f"'{status}'" not in definition


@pytest.mark.parametrize("raw", [False, True])
def test_failure_records_error_and_verified_retry_clears_it(catalog_database, raw):
    """Failure detail lives in error_message; a verified retry clears it."""
    key = _key(f"error-column-{raw}")
    with connect() as conn:
        failed = register_artifact(
            "census.tiger",
            "https://example.test/x",
            f"virtual://{key}/attempt",
            key,
            status="failed",
            error_message="HTTP 503",
            conn=conn if raw else None,
        )
    row = _artifact_row(failed["artifact_id"])
    assert (row["error_message"], row["downloaded_at"]) == ("HTTP 503", None)
    assert "error" not in row["metadata"]
    with connect() as conn:
        promoted = _register(key, "good-bytes", conn=conn if raw else None)
    assert promoted["artifact_id"] == failed["artifact_id"]
    row = _artifact_row(failed["artifact_id"])
    assert row["status"] == "downloaded"
    assert row["error_message"] is None
    assert row["downloaded_at"] is not None
