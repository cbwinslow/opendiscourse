"""Story 3.1 database contract: idempotent, BioGuide-only, evidence-backed identity load."""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from idempotency_harness import (
    IdempotencyCase,
    assert_kill_and_resume_same,
    assert_run_twice_same,
    assert_wipe_and_reload_same,
)
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
        _seed_chamber_organizations()
        yield
    finally:
        # CI runs every DB module against one shared database, and later tests
        # downgrade the schema; the person_identifier downgrade guard refuses
        # while evidence pointers exist. Leave the database as we found it.
        _remove_loaded_rows()
        with connect() as conn:
            conn.execute("DELETE FROM core.organization WHERE metadata->>'test_seed' = 'true'")
            conn.commit()
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


_TEST_ORGS = (("lower", "House"), ("upper", "Senate"))


def _seed_chamber_organizations() -> None:
    """The House and Senate come from the OpenStates baseline; the test DB has none."""
    with connect() as conn:
        for kind, name in _TEST_ORGS:
            exists = conn.execute(
                "SELECT 1 FROM core.organization WHERE organization_type = %s AND jurisdiction_geoid = 'us'",
                (kind,),
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO core.organization (organization_type, name, jurisdiction_geoid, metadata) "
                    "VALUES (%s, %s, 'us', '{\"test_seed\": true}')",
                    (kind, name),
                )
        conn.commit()


def _remove_loaded_rows() -> None:
    """Delete rows this module's loads created, children before parents."""
    with connect() as conn:
        for statement in (
            "DELETE FROM ingest.identity_conflict WHERE dataset_id = 'congress.legislators'",
            (
                "DELETE FROM core.membership WHERE source_artifact_id IN "
                "(SELECT artifact_id FROM ingest.artifact WHERE dataset_id = 'congress.legislators')"
            ),
            (
                "DELETE FROM core.post WHERE source_artifact_id IN "
                "(SELECT artifact_id FROM ingest.artifact WHERE dataset_id = 'congress.legislators')"
            ),
            (
                "DELETE FROM core.division WHERE source_artifact_id IN "
                "(SELECT artifact_id FROM ingest.artifact WHERE dataset_id = 'congress.legislators')"
            ),
            (
                "DELETE FROM core.person_identifier WHERE source_artifact_id IN "
                "(SELECT artifact_id FROM ingest.artifact WHERE dataset_id = 'congress.legislators') "
                "OR source_run_id IN (SELECT run_id FROM ingest.run WHERE dataset_id = 'congress.legislators')"
            ),
            "DELETE FROM core.person WHERE metadata->>'canonical_baseline' = 'congress-legislators'",
            (
                "DELETE FROM ingest.run_target WHERE run_id IN "
                "(SELECT run_id FROM ingest.run WHERE dataset_id = 'congress.legislators')"
            ),
            "DELETE FROM ingest.run WHERE dataset_id = 'congress.legislators'",
            "DELETE FROM ingest.artifact WHERE dataset_id = 'congress.legislators'",
        ):
            conn.execute(statement)
        conn.commit()


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
        if e.get("terms"):
            out.append("  terms:")
            out.extend(f"  - {json.dumps(t)}" for t in e["terms"])  # JSON is valid YAML flow
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
    connector = LegislatorsConnector(
        vendor_dir=vendor, retain_dir=tmp_path / "retain", expected_origin=None
    )
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


def test_identifier_owned_by_the_only_other_person_attaches_the_rest_to_it(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-0005: a person is found by any identifier the source asserts, never by name."""
    bg = _bioguide()
    owner = _seed_person("Someone Else", fec=f"C{bg}")
    before = _person_count()
    vendor = _vendor(
        tmp_path, [{"bioguide": bg, "ids": {"fec": f"C{bg}", "govtrack": f"c{bg}"}}], [{"bioguide": _bioguide()}]
    )
    connector = _load(tmp_path, monkeypatch, vendor)

    assert _identifier("fec", f"C{bg}")["person_id"] == owner  # not moved
    assert _identifier("bioguide", bg)["person_id"] == owner  # attached to the person who held the fec id
    assert _identifier("govtrack", f"c{bg}")["person_id"] == owner
    assert _person_count() == before + 1  # only the historical newcomer
    assert connector.result["conflicts"] == []


def test_identifiers_split_across_two_persons_are_recorded_not_guessed(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    holder = _seed_person("Holds the fec id", fec=f"C{bg}")
    bioguide_owner = _seed_person("Holds the bioguide id", bg)
    before = _person_count()
    vendor = _vendor(
        tmp_path, [{"bioguide": bg, "ids": {"fec": f"C{bg}", "govtrack": f"c{bg}"}}], [{"bioguide": _bioguide()}]
    )
    connector = _load(tmp_path, monkeypatch, vendor)

    assert _identifier("fec", f"C{bg}")["person_id"] == holder
    assert _identifier("bioguide", bg)["person_id"] == bioguide_owner
    assert _identifier("govtrack", f"c{bg}") is None  # nothing written for the conflicting record
    assert _person_count() == before + 1  # only the historical newcomer, no split person
    [conflict] = connector.result["conflicts"]
    assert conflict["bioguide"] == bg and conflict["kind"] == "multiple_owners"
    assert conflict["person_ids"] == sorted(str(p) for p in (holder, bioguide_owner))
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
    rows = [(bg, "Doomed Person", None, None, "bioguide", bg, uuid.uuid4(), uuid.uuid4())]  # no such artifact/run
    with connect() as conn, pytest.raises(Exception, match="foreign key"):
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


def _latest_run() -> dict:
    with connect() as conn:
        return conn.execute(
            "SELECT run_id, status, record_count, error_message, parameters FROM ingest.run "
            "WHERE dataset_id = 'congress.legislators' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()


def test_successful_run_is_recorded_and_stamped_on_new_identifiers(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    vendor = _vendor(tmp_path, [{"bioguide": bg}], [{"bioguide": _bioguide()}])
    _load(tmp_path, monkeypatch, vendor)
    run = _latest_run()
    assert (run["status"], run["record_count"]) == ("succeeded", 2)
    assert _identifier("bioguide", bg)["source_run_id"] == run["run_id"]
    with connect() as conn:
        targets = {
            r["target"]: r
            for r in conn.execute(
                "SELECT target, rows_inserted, status FROM ingest.run_target WHERE run_id = %s",
                (run["run_id"],),
            ).fetchall()
        }
    assert targets["core.person"]["rows_inserted"] == 2
    assert targets["core.person_identifier"]["status"] == "succeeded"


def test_provenance_survives_a_same_bytes_rerun_on_a_newer_commit(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    vendor = _vendor(tmp_path, [{"bioguide": bg}], [{"bioguide": _bioguide()}])
    _load(tmp_path, monkeypatch, vendor)
    first = _latest_run()
    _git(vendor, "commit", "-q", "--allow-empty", "-m", "upstream moved, bytes did not")
    _load(tmp_path, monkeypatch, vendor)
    assert _latest_run()["run_id"] != first["run_id"]
    # The identifier still resolves to the run (and commit) that first asserted it.
    stamped = _identifier("bioguide", bg)["source_run_id"]
    assert stamped == first["run_id"]
    with connect() as conn:
        commit = conn.execute(
            "SELECT parameters->>'commit' AS c FROM ingest.run WHERE run_id = %s", (stamped,)
        ).fetchone()["c"]
    assert commit == first["parameters"]["commit"]


def test_interrupt_before_publish_marks_run_failed(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(self, ctx):  # KeyboardInterrupt is not an Exception
        raise KeyboardInterrupt

    monkeypatch.setattr(LegislatorsConnector, "stage", interrupted)
    vendor = _vendor(tmp_path, [{"bioguide": _bioguide()}], [{"bioguide": _bioguide()}])
    with pytest.raises(KeyboardInterrupt):
        _load(tmp_path, monkeypatch, vendor)
    assert _latest_run()["status"] == "failed"


def test_error_with_empty_message_still_marks_run_failed(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def blank(self, ctx):
        raise ValueError()

    monkeypatch.setattr(LegislatorsConnector, "normalize", blank)
    vendor = _vendor(tmp_path, [{"bioguide": _bioguide()}], [{"bioguide": _bioguide()}])
    with pytest.raises(ValueError):
        _load(tmp_path, monkeypatch, vendor)
    assert _latest_run()["status"] == "failed"


def test_run_with_conflicts_is_partial_and_report_is_per_run(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    _seed_person("Holder", fec=f"P{bg}")
    _seed_person("Owner", bg)
    vendor = _vendor(
        tmp_path, [{"bioguide": bg, "ids": {"fec": f"P{bg}"}}], [{"bioguide": _bioguide()}]
    )
    connector = _load(tmp_path, monkeypatch, vendor)
    run = _latest_run()
    assert run["status"] == "partial"
    assert str(run["run_id"]) in connector.result["report"]


def test_truncated_or_empty_yaml_fails_closed_without_writes(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = _person_count()
    vendor = _vendor(tmp_path, [{"bioguide": _bioguide()}], [{"bioguide": _bioguide()}])
    (vendor / "legislators-historical.yaml").write_text("")
    _git(vendor, "add", "-A")
    _git(vendor, "commit", "-q", "-m", "empty")
    with pytest.raises(ValueError, match="YAML list"):
        _load(tmp_path, monkeypatch, vendor)
    assert _person_count() == before
    assert _latest_run()["status"] == "failed"


def test_assume_unchanged_edit_is_still_detected(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vendor = _vendor(tmp_path, [{"bioguide": _bioguide()}], [{"bioguide": _bioguide()}])
    _git(vendor, "update-index", "--assume-unchanged", "legislators-current.yaml")
    (vendor / "legislators-current.yaml").write_text(_yaml([{"bioguide": _bioguide()}]))
    with pytest.raises(RuntimeError, match="differs from upstream commit"):
        _load(tmp_path, monkeypatch, vendor)


def test_wrong_origin_or_unpushed_head_is_refused(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vendor = _vendor(tmp_path, [{"bioguide": _bioguide()}], [{"bioguide": _bioguide()}])
    _git(vendor, "remote", "add", "origin", "https://github.com/someone/fork.git")
    strict = LegislatorsConnector(vendor_dir=vendor, retain_dir=tmp_path / "retain")
    with pytest.raises(RuntimeError, match="origin is"):
        run_connector(strict)
    _git(vendor, "remote", "set-url", "origin", "git@github.com:unitedstates/congress-legislators.git")
    with pytest.raises(RuntimeError, match="not on any remote branch"):
        run_connector(LegislatorsConnector(vendor_dir=vendor, retain_dir=tmp_path / "retain"))


def _legislator_snapshot() -> dict:
    """Natural-key digest of what the loader wrote: no surrogate ids, no timestamps."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT bg.external_id AS bioguide, i.namespace, i.external_id, p.full_name "
            "FROM core.person_identifier i "
            "JOIN core.person p ON p.person_id = i.person_id "
            "JOIN core.person_identifier bg ON bg.person_id = p.person_id AND bg.namespace = 'bioguide' "
            "WHERE i.source_artifact_id IN "
            "(SELECT artifact_id FROM ingest.artifact WHERE dataset_id = 'congress.legislators') "
            "ORDER BY 1, 2, 3"
        ).fetchall()
        people = conn.execute(
            "SELECT count(*) AS n FROM core.person WHERE metadata->>'canonical_baseline' = 'congress-legislators'"
        ).fetchone()["n"]
        terms = conn.execute(
            "SELECT bg.external_id AS bioguide, o.organization_type, m.role, m.start_date, m.end_date, "
            "p.label, d.ocd_division_id, m.metadata::text "
            "FROM core.membership m "
            "JOIN core.person_identifier bg ON bg.person_id = m.person_id AND bg.namespace = 'bioguide' "
            "JOIN core.organization o ON o.organization_id = m.organization_id "
            "LEFT JOIN core.post p ON p.post_id = m.post_id "
            "LEFT JOIN core.division d ON d.division_id = p.division_id "
            "WHERE m.source_artifact_id IN "
            "(SELECT artifact_id FROM ingest.artifact WHERE dataset_id = 'congress.legislators') "
            "ORDER BY 1, 3, 4"
        ).fetchall()
    import hashlib

    digest = hashlib.md5(repr([tuple(r.values()) for r in rows]).encode()).hexdigest()
    term_digest = hashlib.md5(repr([tuple(r.values()) for r in terms]).encode()).hexdigest()
    return {
        "people": people,
        "identifiers": len(rows),
        "digest": digest,
        "memberships": len(terms),
        "membership_digest": term_digest,
    }


def _legislator_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, point: int, atomic: bool):
    from contextlib import contextmanager

    from opendiscourse_research.ingestion import legislators as module

    bg = [_bioguide(), _bioguide(), _bioguide()]
    vendor = _vendor(
        tmp_path,
        [
            {
                "bioguide": bg[0],
                "ids": {"govtrack": f"h{bg[0]}", "fec": [f"H{bg[0]}A", f"H{bg[0]}B"]},
                "terms": [HOUSE_WA7, SENATE_WA],
            },
            {"bioguide": bg[1], "terms": [{**HOUSE_WA7, "district": 0, "state": "AK"}]},
        ],
        [{"bioguide": bg[2], "ids": {"icpsr": f"h{bg[2]}"}, "terms": [{**HOUSE_WA7, "district": -1}]}],
    )
    real = module.promote_legislators

    @contextmanager
    def interrupt(where: int):
        def killed(conn, rows):
            if where == 0:
                raise RuntimeError("killed before publish wrote anything")
            real(conn, rows)  # the data transaction commits...
            raise RuntimeError("killed before the artifacts were marked loaded")  # ...then the process dies

        with monkeypatch.context() as patch:
            patch.setattr(module, "promote_legislators", killed)
            yield

    return IdempotencyCase(
        name="congress.legislators",
        load=lambda: _load(tmp_path, monkeypatch, vendor),
        snapshot=_legislator_snapshot,
        wipe=_remove_loaded_rows,
        interrupt=interrupt,
        points=(point,),
        atomic=atomic,
    )


def test_legislators_run_twice_and_wipe_and_reload_are_idempotent(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = _legislator_case(tmp_path, monkeypatch, point=0, atomic=True)
    assert_run_twice_same(case)
    assert_wipe_and_reload_same(case)


def test_legislators_killed_before_publish_leaves_no_data_and_resumes(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert_kill_and_resume_same(_legislator_case(tmp_path, monkeypatch, point=0, atomic=True))


def test_legislators_killed_after_commit_before_artifacts_loaded_converges(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Partial by nature: the data transaction is committed, the artifact status flip is not.
    assert_kill_and_resume_same(_legislator_case(tmp_path, monkeypatch, point=1, atomic=False))


# -- Story 3.3: terms -> memberships on posts and divisions ------------------------
def _memberships(bioguide: str) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "SELECT m.role, m.start_date, m.end_date, m.metadata, m.source_artifact_id, o.organization_type, "
            "p.label AS post_label, p.role AS post_role, d.ocd_division_id, d.label AS division_label, "
            "d.classification, pd.ocd_division_id AS post_division_ocd "
            "FROM core.membership m "
            "JOIN core.person_identifier i ON i.person_id = m.person_id AND i.namespace = 'bioguide' "
            "JOIN core.organization o ON o.organization_id = m.organization_id "
            "LEFT JOIN core.post p ON p.post_id = m.post_id "
            "LEFT JOIN core.division d ON d.division_id = p.division_id "
            "LEFT JOIN core.division pd ON pd.division_id = p.division_id "
            "WHERE i.external_id = %s ORDER BY m.start_date",
            (bioguide,),
        ).fetchall()


HOUSE_WA7 = {"type": "rep", "start": "2019-01-03", "end": "2021-01-03", "state": "WA", "district": 7, "party": "Democrat"}
SENATE_WA = {"type": "sen", "start": "2025-01-03", "end": "2031-01-03", "state": "WA", "class": 1, "party": "Democrat", "state_rank": "junior"}


def test_terms_become_memberships_on_posts_and_divisions_with_evidence(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    at_large = {"type": "rep", "start": "2001-01-03", "end": "2003-01-03", "state": "AK", "district": 0}
    unknown = {"type": "rep", "start": "1851-03-04", "end": "1853-03-04", "state": "OH", "district": -1}
    delegate = {"type": "rep", "start": "1999-01-03", "end": "2001-01-03", "state": "DC", "district": 0}
    vendor = _vendor(
        tmp_path,
        [{"bioguide": bg, "terms": [unknown, delegate, at_large, HOUSE_WA7, SENATE_WA]}],
        [{"bioguide": _bioguide()}],
    )
    connector = _load(tmp_path, monkeypatch, vendor)

    assert connector.result["memberships_created"] == 5 and connector.result["terms_unresolved"] == 0
    old, dc, ak, wa7, wa_sen = _memberships(bg)
    assert (old["organization_type"], old["post_label"], old["metadata"]) == (
        "lower", None, {"state": "OH", "district": -1},
    )
    assert (dc["post_label"], dc["ocd_division_id"], dc["classification"]) == (
        "Representative, DC", "ocd-division/country:us/district:dc", "district",
    )
    assert (ak["post_label"], ak["ocd_division_id"]) == ("Representative, AK-AL", "ocd-division/country:us/state:ak/cd:at-large")
    assert (wa7["role"], wa7["organization_type"], wa7["post_label"], wa7["ocd_division_id"]) == (
        "representative", "lower", "Representative, WA-7", "ocd-division/country:us/state:wa/cd:7",
    )
    assert wa7["division_label"] == "Washington's 7th congressional district" and wa7["classification"] == "cd"
    assert (str(wa7["start_date"]), str(wa7["end_date"])) == ("2019-01-03", "2021-01-03")
    assert wa7["metadata"] == {"state": "WA", "district": 7, "party": "Democrat"}
    assert (wa_sen["role"], wa_sen["organization_type"], wa_sen["post_label"], wa_sen["ocd_division_id"]) == (
        "senator", "upper", "Senator, Class 1", "ocd-division/country:us/state:wa",
    )
    assert wa_sen["metadata"]["state_rank"] == "junior" and wa_sen["metadata"]["senate_class"] == 1
    # every term is asserted by the artifact of the file it came from
    current = _identifier("bioguide", bg)["source_artifact_id"]  # this person came from the current file
    assert {m["source_artifact_id"] for m in (old, dc, ak, wa7, wa_sen)} == {current}
    # the state division is shared by the district post and the Senate post, not duplicated
    assert _one_count("SELECT count(*) AS n FROM core.division WHERE ocd_division_id = 'ocd-division/country:us/state:wa'") == 1
    ledger = _ledger("core.membership")
    assert ledger == ("succeeded", 5, 0, 0)


def _one_count(sql: str, *params: object) -> int:
    with connect() as conn:
        return conn.execute(sql, params).fetchone()["n"]


def _ledger(target: str) -> tuple:
    with connect() as conn:
        row = conn.execute(
            "SELECT t.status, t.rows_inserted, t.rows_updated, t.rows_skipped FROM ingest.run_target t "
            "JOIN ingest.run r USING (run_id) WHERE r.dataset_id = 'congress.legislators' AND t.target = %s "
            "ORDER BY r.started_at DESC LIMIT 1",
            (target,),
        ).fetchone()
    return tuple(row.values())


def test_two_at_large_members_share_one_post(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b = _bioguide(), _bioguide()
    term = {"type": "rep", "start": "1913-03-04", "end": "1915-03-04", "state": "WA", "district": 0}
    vendor = _vendor(tmp_path, [{"bioguide": a, "terms": [term]}], [{"bioguide": b, "terms": [term]}])
    _load(tmp_path, monkeypatch, vendor)

    (first,), (second,) = _memberships(a), _memberships(b)
    assert first["post_label"] == second["post_label"] == "Representative, WA-AL"
    assert _one_count(
        "SELECT count(*) AS n FROM core.post p JOIN core.division d USING (division_id) "
        "WHERE d.ocd_division_id = 'ocd-division/country:us/state:wa/cd:at-large' AND p.label = 'Representative, WA-AL'"
    ) == 1


def test_rerun_with_same_bytes_changes_no_membership(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    vendor = _vendor(tmp_path, [{"bioguide": bg, "terms": [HOUSE_WA7, SENATE_WA]}], [{"bioguide": _bioguide()}])
    _load(tmp_path, monkeypatch, vendor)
    before = _memberships(bg)

    second = _load(tmp_path, monkeypatch, vendor)

    assert (second.result["memberships_created"], second.result["memberships_updated"]) == (0, 0)
    assert second.result["memberships_unchanged"] == 2
    assert second.result["divisions_created"] == 0 and second.result["posts_created"] == 0
    assert _memberships(bg) == before
    assert _ledger("core.membership") == ("succeeded", 0, 0, 2)


def test_upstream_edit_updates_the_term_and_adds_the_new_one(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    vendor = _vendor(tmp_path, [{"bioguide": bg, "terms": [HOUSE_WA7]}], [{"bioguide": _bioguide()}])
    _load(tmp_path, monkeypatch, vendor)
    (before,) = _memberships(bg)
    resigned = {**HOUSE_WA7, "end": "2020-06-01", "party": "Independent"}
    later = {**HOUSE_WA7, "start": "2021-01-03", "end": "2023-01-03"}
    _vendor(tmp_path, [{"bioguide": bg, "terms": [resigned, later]}], [{"bioguide": _bioguide()}])

    second = _load(tmp_path, monkeypatch, vendor)

    assert (second.result["memberships_created"], second.result["memberships_updated"]) == (1, 1)
    first, new = _memberships(bg)
    assert str(first["end_date"]) == "2020-06-01" and first["metadata"]["party"] == "Independent"
    assert first["source_artifact_id"] != before["source_artifact_id"]  # evidence moved to the new version
    assert str(new["start_date"]) == "2021-01-03"
    assert _ledger("core.membership") == ("succeeded", 1, 1, 0)


def test_an_unknown_jurisdiction_is_reported_not_guessed_and_the_run_is_partial(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    odd = {"type": "rep", "start": "1900-03-04", "end": "1901-03-04", "state": "ZZ", "district": 1}
    vendor = _vendor(tmp_path, [{"bioguide": bg, "terms": [HOUSE_WA7, odd]}], [{"bioguide": _bioguide()}])
    connector = _load(tmp_path, monkeypatch, vendor)

    assert [m["post_label"] for m in _memberships(bg)] == ["Representative, WA-7"]
    assert connector.result["terms_unknown_jurisdiction"] == [
        {"bioguide": bg, "state": "ZZ", "start": "1900-03-04", "file": "legislators-current.yaml"}
    ]
    assert _ledger("core.membership")[0] == "partial"
    with connect() as conn:
        status = conn.execute(
            "SELECT status FROM ingest.run WHERE dataset_id = 'congress.legislators' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()["status"]
    assert status == "partial"
    assert Path(connector.result["report"]).is_file()


def test_missing_chamber_organizations_fail_before_any_write_with_the_fix_named(
    catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bg = _bioguide()
    vendor = _vendor(tmp_path, [{"bioguide": bg, "terms": [HOUSE_WA7]}], [{"bioguide": _bioguide()}])
    with connect() as conn:
        conn.execute("UPDATE core.organization SET jurisdiction_geoid = 'xx' WHERE organization_type = 'lower'")
        conn.commit()
    try:
        with pytest.raises(RuntimeError, match="load-openstates-organizations"):
            _load(tmp_path, monkeypatch, vendor)
    finally:
        with connect() as conn:
            conn.execute("UPDATE core.organization SET jurisdiction_geoid = 'us' WHERE organization_type = 'lower'")
            conn.commit()
    assert _memberships(bg) == []
