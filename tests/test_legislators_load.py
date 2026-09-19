"""Story 3.1 database contract: idempotent, BioGuide-only, evidence-backed identity load."""

from __future__ import annotations

import itertools
import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, connect, session
from opendiscourse_research.ingestion.connector import run_connector
from opendiscourse_research.ingestion.legislators import LegislatorsConnector
from opendiscourse_research.models.catalog import artifact_table
from opendiscourse_research.models.core import person_identifier_table, person_table
from opendiscourse_research.repositories.people import promote_legislators

_counter = itertools.count(1)
_RUN = uuid.uuid4().int % 90 + 10  # keeps ids unique across reruns on a persistent DB


def _bioguide() -> str:
    return f"T{_RUN:02d}{next(_counter):04d}"


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    """Use CI's PostGIS service or a disposable local one, as the 1.6 contract tests do."""
    original = settings.database_url
    external = os.environ.get("OPENDISCOURSE_TEST_DATABASE_URL")
    if external:
        settings.database_url = external
        container = None
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
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


def _yaml(entries: list[dict]) -> str:
    out = []
    for e in entries:
        out.append(f"- id:\n    bioguide: {e['bioguide']}")
        for ns, val in e.get("ids", {}).items():
            vals = val if isinstance(val, list) else [val]
            out.append(f"    {ns}:" if len(vals) > 1 else f"    {ns}: '{vals[0]}'")
            if len(vals) > 1:
                out.extend(f"    - '{v}'" for v in vals)
        out.append(f"  name:\n    first: {e.get('first', 'Given')}\n    last: {e.get('last', 'Family')}")
    return "\n".join(out) + "\n"


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)


def _vendor(tmp_path: Path, current: list[dict], historical: list[dict]) -> Path:
    vendor = tmp_path / "vendor"
    vendor.mkdir(exist_ok=True)
    if not (vendor / ".git").exists():
        _git(vendor, "init", "-q")
        _git(vendor, "config", "user.email", "t@example.com")
        _git(vendor, "config", "user.name", "t")
    (vendor / "legislators-current.yaml").write_text(_yaml(current))
    (vendor / "legislators-historical.yaml").write_text(_yaml(historical))
    _git(vendor, "add", "-A")
    _git(vendor, "commit", "-q", "-m", "data", "--allow-empty")
    return vendor


def _load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vendor: Path) -> LegislatorsConnector:
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake" / "raw"))
    connector = LegislatorsConnector(vendor_dir=vendor, retain_dir=tmp_path / "retain")
    run_connector(connector)
    return connector


def _identifier(namespace: str, external_id: str):
    table = person_identifier_table()
    with session() as s:
        return s.execute(
            select(table).where(table.c.namespace == namespace, table.c.external_id == external_id)
        ).mappings().first()


def _seed_person(name: str, bioguide: str | None = None, **ids: str) -> uuid.UUID:
    person, ident = person_table(), person_identifier_table()
    with session() as s:
        pid = s.execute(person.insert().values(full_name=name).returning(person.c.person_id)).scalar_one()
        if bioguide:
            s.execute(ident.insert().values(person_id=pid, namespace="bioguide", external_id=bioguide))
        for ns, ext in ids.items():
            s.execute(ident.insert().values(person_id=pid, namespace=ns, external_id=ext))
    return pid


def _person_count() -> int:
    with session() as s:
        return s.execute(select(func.count()).select_from(person_table())).scalar_one()


def _artifacts() -> list[dict]:
    table = artifact_table()
    with session() as s:
        return [
            dict(r)
            for r in s.execute(
                select(table).where(table.c.dataset_id == "congress.legislators")
            ).mappings()
        ]


def test_fresh_legislator_gets_person_and_evidence_backed_identifiers(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    vendor = _vendor(
        tmp_path,
        [{"bioguide": bg, "ids": {"govtrack": f"g{bg}", "fec": [f"F{bg}A", f"F{bg}B"]}, "first": "Fresh", "last": "Face"}],
        [{"bioguide": _bioguide()}],
    )
    connector = _load(tmp_path, monkeypatch, vendor)

    row = _identifier("bioguide", bg)
    assert row is not None and row["source_artifact_id"] is not None
    assert _identifier("fec", f"F{bg}B")["person_id"] == row["person_id"]
    with session() as s:
        person = s.execute(
            select(person_table()).where(person_table().c.person_id == row["person_id"])
        ).mappings().one()
    assert (person["full_name"], person["given_name"]) == ("Fresh Face", "Fresh")
    assert connector.result["people_created"] == 2

    artifact = next(a for a in _artifacts() if a["artifact_id"] == row["source_artifact_id"])
    assert artifact["status"] == "loaded" and artifact["checksum_sha256"]
    assert artifact["remote_url"].endswith("/legislators-current.yaml")
    assert artifact["metadata"]["upstream_commit"] in artifact["remote_url"]
    assert Path(artifact["local_path"]).is_file()


def test_existing_person_matched_by_bioguide_is_not_rewritten(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    pid = _seed_person("Baseline Name", bg, govtrack=f"old{bg}")
    before = _person_count()
    vendor = _vendor(
        tmp_path,
        [{"bioguide": bg, "ids": {"govtrack": f"new{bg}", "wikidata": f"Q{bg}"}, "first": "Other", "last": "Name"}],
        [{"bioguide": _bioguide()}],
    )
    _load(tmp_path, monkeypatch, vendor)

    assert _person_count() == before + 1  # only the historical newcomer
    with session() as s:
        name = s.execute(select(person_table().c.full_name).where(person_table().c.person_id == pid)).scalar_one()
    assert name == "Baseline Name"
    assert _identifier("bioguide", bg)["source_artifact_id"] is None  # baseline evidence untouched
    old = _identifier("govtrack", f"old{bg}")
    assert old["person_id"] == pid and old["source_artifact_id"] is None  # never rewritten
    assert _identifier("govtrack", f"new{bg}")["person_id"] == pid  # added beside it, not replacing
    added = _identifier("wikidata", f"Q{bg}")
    assert added["person_id"] == pid and added["source_artifact_id"] is not None


def test_same_name_without_bioguide_is_never_merged(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    namesake = _seed_person("Twin Person")
    bg = _bioguide()
    vendor = _vendor(
        tmp_path, [{"bioguide": bg, "first": "Twin", "last": "Person"}], [{"bioguide": _bioguide()}]
    )
    _load(tmp_path, monkeypatch, vendor)
    assert _identifier("bioguide", bg)["person_id"] != namesake


def test_rerun_with_same_bytes_changes_nothing(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vendor = _vendor(
        tmp_path,
        [{"bioguide": _bioguide(), "ids": {"govtrack": f"r{next(_counter)}"}}],
        [{"bioguide": _bioguide()}],
    )
    _load(tmp_path, monkeypatch, vendor)
    people, versions = _person_count(), {a["artifact_id"]: a["artifact_version"] for a in _artifacts()}
    second = _load(tmp_path, monkeypatch, vendor)

    assert (second.result["people_created"], second.result["identifiers_created"]) == (0, 0)
    assert _person_count() == people
    assert {a["artifact_id"]: a["artifact_version"] for a in _artifacts()} == versions


def test_changed_upstream_appends_version_and_adds_only_new_identifiers(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg, hist = _bioguide(), _bioguide()
    vendor = _vendor(tmp_path, [{"bioguide": bg}], [{"bioguide": hist}])
    _load(tmp_path, monkeypatch, vendor)
    old = {a["artifact_id"] for a in _artifacts()}
    _vendor(tmp_path, [{"bioguide": bg, "ids": {"icpsr": f"i{bg}"}}], [{"bioguide": hist}])
    second = _load(tmp_path, monkeypatch, vendor)

    assert second.result["people_created"] == 0 and second.result["identifiers_created"] == 1
    new_row = _identifier("icpsr", f"i{bg}")
    assert new_row["source_artifact_id"] not in old  # new bytes, new artifact version
    kept = [a for a in _artifacts() if a["artifact_id"] in old]
    assert all(a["checksum_sha256"] for a in kept)  # earlier evidence retained


def test_identifier_owned_by_another_person_is_reported_not_moved(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    owner = _seed_person("Someone Else", fec=f"C{bg}")
    vendor = _vendor(
        tmp_path, [{"bioguide": bg, "ids": {"fec": f"C{bg}", "govtrack": f"c{bg}"}}], [{"bioguide": _bioguide()}]
    )
    connector = _load(tmp_path, monkeypatch, vendor)

    assert _identifier("fec", f"C{bg}")["person_id"] == owner
    assert _identifier("govtrack", f"c{bg}")["person_id"] == _identifier("bioguide", bg)["person_id"]
    [conflict] = connector.result["conflicts"]
    assert conflict["bioguide"] == bg and conflict["existing_person_id"] == str(owner)
    assert Path(connector.result["report"]).is_file()


def test_shared_upstream_identifier_is_skipped_for_both_people(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = _bioguide(), _bioguide()
    shared = f"S{a}"
    vendor = _vendor(
        tmp_path, [{"bioguide": a, "ids": {"fec": shared}}, {"bioguide": b, "ids": {"fec": shared, "govtrack": f"s{b}"}}],
        [{"bioguide": _bioguide()}],
    )
    connector = _load(tmp_path, monkeypatch, vendor)
    assert _identifier("fec", shared) is None
    assert _identifier("govtrack", f"s{b}") is not None
    assert connector.result["shared_upstream_identifiers"][0]["bioguide_ids"] == sorted([a, b])


def test_malformed_bioguide_fails_before_any_write_and_marks_run_failed(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _person_count()
    vendor = _vendor(tmp_path, [{"bioguide": "bad-id"}], [{"bioguide": _bioguide()}])
    with pytest.raises(ValueError, match="malformed BioGuide"):
        _load(tmp_path, monkeypatch, vendor)
    assert _person_count() == before
    with connect() as conn:
        status = conn.execute(
            "SELECT status, error_message FROM ingest.run WHERE dataset_id = 'congress.legislators' "
            "ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    assert status["status"] == "failed" and "malformed" in status["error_message"]


def test_locally_modified_checkout_is_refused(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vendor = _vendor(tmp_path, [{"bioguide": _bioguide()}], [{"bioguide": _bioguide()}])
    (vendor / "legislators-current.yaml").write_text("- edited\n")
    with pytest.raises(RuntimeError, match="differs from upstream commit"):
        _load(tmp_path, monkeypatch, vendor)


def test_missing_checkout_gives_actionable_error(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(FileNotFoundError, match="bootstrap_upstream.sh"):
        _load(tmp_path, monkeypatch, tmp_path / "nowhere")


def test_failed_publish_rolls_back_every_write(catalog_database: None) -> None:
    bg, before = _bioguide(), _person_count()
    rows = [(bg, "Doomed Person", None, None, "bioguide", bg, uuid.uuid4())]  # artifact does not exist
    with connect() as conn, pytest.raises(Exception, match="artifact"):
        promote_legislators(conn, rows)
    assert _person_count() == before
    assert _identifier("bioguide", bg) is None


def test_migration_column_is_nullable_and_indexed(catalog_database: None) -> None:
    with session() as s:
        nullable = s.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns WHERE table_schema='core' "
                "AND table_name='person_identifier' AND column_name='source_artifact_id'"
            )
        ).scalar_one()
        index = s.execute(
            text("SELECT 1 FROM pg_indexes WHERE indexname='person_identifier_source_artifact_idx'")
        ).first()
    assert nullable == "YES" and index is not None


def test_damaged_retained_copy_fails_and_is_left_untouched(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from opendiscourse_research.artifact_storage import file_checksum, retained_path

    vendor = _vendor(tmp_path, [{"bioguide": _bioguide()}], [{"bioguide": _bioguide()}])
    checksum = file_checksum(vendor / "legislators-current.yaml")
    damaged = retained_path(tmp_path / "retain" / "legislators-current.yaml", checksum)
    damaged.parent.mkdir(parents=True)
    damaged.write_text("not the evidence\n")
    before = _person_count()
    with pytest.raises(ValueError, match="never overwritten"):
        _load(tmp_path, monkeypatch, vendor)
    assert damaged.read_text() == "not the evidence\n"
    assert _person_count() == before
