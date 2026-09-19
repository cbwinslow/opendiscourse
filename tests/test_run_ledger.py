"""Story 9.2: every run records code_version and what it wrote, per target and slice."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, connect, session
from opendiscourse_research.ingestion.base import IngestionRun, code_version
from opendiscourse_research.repositories.runs import loaded_coverage

DATASET = "bls.cpi"  # any catalog dataset; runs are tagged so cleanup finds only ours


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    """CI's shared PostGIS service, or a disposable local one."""
    original = settings.database_url
    external = os.environ.get("OPENDISCOURSE_TEST_DATABASE_URL")
    container = None
    if external:
        settings.database_url = external
    else:
        postgres = pytest.importorskip("testcontainers.postgres")
        container = postgres.PostgresContainer(
            "postgis/postgis:17-3.5", username="test", password="test", dbname="test"
        )
        container.start()
        settings.database_url = container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql://", 1
        )
    try:
        apply_migrations()
        sync_inventory()
        yield
    finally:
        # The shared database is downgraded by later tests; the ledger's downgrade
        # guard refuses while rows exist, so remove what these tests wrote.
        with connect() as conn:
            conn.execute(
                "DELETE FROM ingest.run_target WHERE run_id IN "
                "(SELECT run_id FROM ingest.run WHERE parameters->>'ledger_test' = 'true')"
            )
            conn.execute("DELETE FROM ingest.run WHERE parameters->>'ledger_test' = 'true'")
            conn.commit()
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


def _run(fail: bool = False) -> IngestionRun:
    run = IngestionRun(DATASET, {"ledger_test": "true"}, mode="manual")
    try:
        with run:
            if fail:
                raise RuntimeError("boom")
    except RuntimeError:
        pass
    return run


def _rows(run: IngestionRun) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "SELECT target, coverage_key, status, rows_inserted, rows_updated, rows_skipped "
            "FROM ingest.run_target WHERE run_id = %s ORDER BY target, coverage_key",
            (run.run_id,),
        ).fetchall()


def test_every_new_run_carries_the_code_version(catalog_database: None) -> None:
    run = _run()
    with connect() as conn:
        stamped = conn.execute(
            "SELECT code_version FROM ingest.run WHERE run_id = %s", (run.run_id,)
        ).fetchone()["code_version"]
    assert stamped == code_version() and stamped not in ("", None)


def test_record_target_writes_counts_and_is_idempotent_per_key(catalog_database: None) -> None:
    run = IngestionRun(DATASET, {"ledger_test": "true"})
    with run:
        run.record_target("core.bill", "congress=118", inserted=10, updated=2, skipped=5)
        run.record_target("core.bill", "congress=119", inserted=1)
        run.record_target("core.bill", "congress=118", inserted=11, updated=2, skipped=5)  # retry
    rows = _rows(run)
    assert [(r["coverage_key"], r["rows_inserted"]) for r in rows] == [
        ("congress=118", 11),
        ("congress=119", 1),
    ]


def test_ledger_rejects_bad_status_and_negative_counts(catalog_database: None) -> None:
    run = IngestionRun(DATASET, {"ledger_test": "true"})
    with run:
        with pytest.raises(IntegrityError, match="run_target_status_check"):
            run.record_target("core.bill", "x", status="done")
        with pytest.raises(IntegrityError, match="run_target_rows_check"):
            run.record_target("core.bill", "y", inserted=-1)


def test_loaded_coverage_answers_what_is_loaded_by_period(catalog_database: None) -> None:
    first = IngestionRun(DATASET, {"ledger_test": "true"})
    with first:
        first.record_target("core.cov_a", "congress=117", inserted=5)
        first.record_target("core.cov_a", "congress=118", inserted=7)
    second = IngestionRun(DATASET, {"ledger_test": "true"})
    with second:
        second.record_target("core.cov_a", "congress=118", inserted=0, skipped=7)
    view = {
        (r["target"], r["coverage_key"]): r for r in loaded_coverage(DATASET) if r["target"] == "core.cov_a"
    }
    assert set(view) == {("core.cov_a", "congress=117"), ("core.cov_a", "congress=118")}
    assert view[("core.cov_a", "congress=117")]["run_id"] == first.run_id
    newest = view[("core.cov_a", "congress=118")]  # newest run wins, older run is not lost
    assert (newest["run_id"], newest["rows_skipped"]) == (second.run_id, 7)
    assert newest["code_version"] == code_version()


def test_failed_targets_are_recorded_but_not_reported_as_loaded(catalog_database: None) -> None:
    run = IngestionRun(DATASET, {"ledger_test": "true"})
    with run:
        run.record_target("core.cov_b", "congress=110", status="failed")
        run.record_target("core.cov_b", "congress=111", inserted=3, status="partial")
    assert [r["status"] for r in _rows(run)] == ["failed", "partial"]
    keys = {r["coverage_key"]: r["status"] for r in loaded_coverage(DATASET) if r["target"] == "core.cov_b"}
    assert keys == {"congress=111": "partial"}


def test_loaded_coverage_can_be_scoped_to_a_dataset(catalog_database: None) -> None:
    run = IngestionRun(DATASET, {"ledger_test": "true"})
    with run:
        run.record_target("core.cov_c", "all", inserted=1)
    assert all(r["dataset_id"] == DATASET for r in loaded_coverage(DATASET))
    assert loaded_coverage("fred.series") == [] or all(
        r["dataset_id"] == "fred.series" for r in loaded_coverage("fred.series")
    )


def test_failed_run_keeps_its_status_and_code_version(catalog_database: None) -> None:
    run = _run(fail=True)
    with connect() as conn:
        row = conn.execute(
            "SELECT status, code_version FROM ingest.run WHERE run_id = %s", (run.run_id,)
        ).fetchone()
    assert row["status"] == "failed" and row["code_version"]


def test_view_and_table_exist_with_lookup_index(catalog_database: None) -> None:
    with session() as s:
        assert s.execute(text("SELECT to_regclass('ingest.loaded_coverage')")).scalar_one()
        assert s.execute(
            text("SELECT 1 FROM pg_indexes WHERE indexname = 'run_target_lookup_idx'")
        ).first()


# -- code_version (no database) ------------------------------------------------


def _repo(tmp_path: Path) -> Path:
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)
    (tmp_path / "f.txt").write_text("a\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "c"], check=True)
    return tmp_path


def test_code_version_is_the_sha_and_marks_tracked_edits_dirty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENDISCOURSE_CODE_VERSION", raising=False)
    code_version.cache_clear()
    repo = _repo(tmp_path)
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert code_version(repo) == sha
    code_version.cache_clear()
    (repo / "f.txt").write_text("b\n")
    assert code_version(repo) == f"{sha}-dirty"
    code_version.cache_clear()


def test_code_version_override_and_no_git_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code_version.cache_clear()
    monkeypatch.setenv("OPENDISCOURSE_CODE_VERSION", "release-1.2")
    assert code_version(tmp_path) == "release-1.2"
    code_version.cache_clear()
    monkeypatch.delenv("OPENDISCOURSE_CODE_VERSION")
    assert code_version(tmp_path) == "unknown"  # not a git checkout
    code_version.cache_clear()
