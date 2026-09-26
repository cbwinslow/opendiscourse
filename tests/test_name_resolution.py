"""Story 10.2 contract: name assertions, the precedence file, the resolver and its write guard (ADR-0005).

The fast tests need no database. The ``db`` tests write only rows that carry ``PREFIX`` or the
``names_test`` marker and remove them again: the database is shared with other test modules.
"""

from __future__ import annotations

import copy
import itertools
import json
import os
import threading
import time
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from alembic import command
from typer.testing import CliRunner

from opendiscourse_research.catalog import sync_inventory, validate_inventory
from opendiscourse_research.cli import app
from opendiscourse_research.config import settings
from opendiscourse_research.db import _alembic_config, _engine, apply_migrations, connect
from opendiscourse_research.identity_merge import SamePerson
from opendiscourse_research.ingestion.base import IngestionRun
from opendiscourse_research import identitygate
from opendiscourse_research.precedence import (
    _display,
    _entries,
    load_precedence,
    precedence_differs,
    sync_precedence,
    validate_precedence,
)
from opendiscourse_research.repositories.names import (
    UnrankedSource,
    apply_resolution,
    resolve_names,
    upsert_geography_name_sources,
    upsert_person_name_sources,
)
from opendiscourse_research.repositories.people import PERSON_REFERENCES, merge_person

db = pytest.mark.db

PREFIX = "zztest-names"
_counter = itertools.count(1)
LEGISLATORS, OPENSTATES, CONGRESS_GOV = "congress.legislators", "openstates.legislation", "congress.legislation"
TIGER, PEP, ACS = "census.tiger", "census.population_estimates", "census.acs_5"


# --------------------------------------------------------------------------- fast: the file


def _dataset_ids() -> set[str]:
    from opendiscourse_research.catalog import load_inventory

    return {d["id"] for p in load_inventory()["providers"] for d in p["datasets"]}


def test_precedence_file_is_valid_and_part_of_the_inventory_check() -> None:
    """The tracked file names real datasets, and `init-db` validates it with the rest."""
    assert validate_precedence(load_precedence(), _dataset_ids()) == []
    assert validate_inventory() == []


def test_person_display_is_common_then_official_with_the_documented_ranks() -> None:
    """Operator decision 2026-09-20: full_name shows the common name; official is the fallback."""
    document = load_precedence()
    assert [row for row in _display(document) if row[0] == "person"] == [
        ("person", "common", 1),
        ("person", "official", 2),
    ]
    person = [row for row in _entries(document) if row[0] == "person"]
    assert [(kind, rank, dataset) for _, kind, _, rank, dataset, _ in person] == [
        ("common", 1, OPENSTATES),
        ("official", 1, LEGISLATORS),
        ("official", 2, CONGRESS_GOV),
        ("official", 3, OPENSTATES),
        # Ranked, and deliberately not in display, so a roster does not change the shown name.
        ("roster", 1, "congress.committee_membership"),
        # Ranked, and deliberately not in display, so a Voteview bioname does not change the shown name.
        ("voteview", 1, "congress.voteview"),
        # Ranked, and deliberately not in display, so a nickname cannot become the shown name.
        ("middle", 1, LEGISLATORS),
        ("suffix", 1, LEGISLATORS),
        ("nickname", 1, LEGISLATORS),
        ("former", 1, LEGISLATORS),
    ]
    geography = {(kind, geography_type): [row[4] for row in rows]
                 for (kind, geography_type), rows in _group(_entries(document), "geography").items()}
    assert geography[("full", "county")] == [TIGER, PEP, ACS]
    assert geography[("short", "county")] == [TIGER]
    assert "zcta" not in {geography_type for _, geography_type in geography}  # ZCTA names are never asserted


def _group(entries: list[tuple], entity: str) -> dict[tuple[str, str], list[tuple]]:
    grouped: dict[tuple[str, str], list[tuple]] = {}
    for row in entries:
        if row[0] == entity:
            grouped.setdefault((row[1], row[2]), []).append(row)
    return grouped


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        (lambda d: d["person"]["kinds"]["official"].append({"dataset": "no.such", "field": "x"}), "no.such"),
        (lambda d: d["person"]["kinds"].update(alias=[{"dataset": OPENSTATES, "field": "x"}]), "alias"),
        (lambda d: d["person"].update(display=["official"]), "kind 'common' is ranked but never displayed"),
        (lambda d: d["person"]["kinds"]["official"].append({"dataset": LEGISLATORS, "field": "x"}), "twice"),
        (lambda d: d["person"]["kinds"]["common"][0].pop("field"), "needs a field"),
        (lambda d: d["geography"]["kinds"]["short"].update(county=[]), "needs an ordered list"),
        (lambda d: d["person"].update(display=["common", "common"]), "each name kind once"),
        (lambda d: d.update(version=2), "version"),
        (lambda d: d.update(extra={}), "unknown top-level key 'extra'"),
    ],
)
def test_precedence_validation_reports_each_kind_of_mistake(edit: Any, message: str) -> None:
    document = copy.deepcopy(load_precedence())
    edit(document)
    errors = validate_precedence(document, _dataset_ids())
    assert any(message in error for error in errors), errors


def test_an_assertion_without_evidence_is_refused_before_it_reaches_the_database() -> None:
    row = {"person_id": uuid.uuid4(), "name_kind": "common", "full_name": "X", "given_name": None,
           "family_name": None, "dataset_id": OPENSTATES, "source_vintage": "2024",
           "artifact_id": None, "payload_id": None, "run_id": uuid.uuid4()}
    with pytest.raises(ValueError, match="artifact or a payload"):
        upsert_person_name_sources(None, [row])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="missing run_id"):
        upsert_person_name_sources(None, [{k: v for k, v in row.items() if k != "run_id"}])  # type: ignore[arg-type]


def _row(**changes: Any) -> dict[str, Any]:
    row = {"person_id": uuid.uuid4(), "name_kind": "common", "full_name": "X", "given_name": None,
           "family_name": None, "dataset_id": OPENSTATES, "source_vintage": "2024",
           "artifact_id": uuid.uuid4(), "payload_id": None, "run_id": uuid.uuid4()}
    return {**row, **changes}


def _geo_row(**changes: Any) -> dict[str, Any]:
    row = {"geography_id": uuid.uuid4(), "name_kind": "short", "name": "X", "dataset_id": TIGER,
           "source_vintage": "2024", "artifact_id": uuid.uuid4(), "payload_id": None, "run_id": uuid.uuid4()}
    return {**row, **changes}


@pytest.mark.parametrize("blank", ["", "   ", "\t\n", None])
def test_a_blank_name_is_refused_before_it_reaches_the_database(blank: str | None) -> None:
    with pytest.raises(ValueError, match="non-blank full_name"):
        upsert_person_name_sources(None, [_row(full_name=blank)])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-blank name"):
        upsert_geography_name_sources(None, [_geo_row(name=blank)])  # type: ignore[arg-type]


@pytest.mark.parametrize("vintage", ["2024-9", "24", "", "2024-09-1", "2024/09", "20240", "2024-09-01T00", " 2024"])
def test_a_vintage_that_is_not_zero_padded_iso_is_refused(vintage: str) -> None:
    with pytest.raises(ValueError, match="zero-padded ISO"):
        upsert_person_name_sources(None, [_row(source_vintage=vintage)])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="zero-padded ISO"):
        upsert_geography_name_sources(None, [_geo_row(source_vintage=vintage)])  # type: ignore[arg-type]


def test_two_values_for_one_key_in_a_batch_are_refused_and_naming_the_key() -> None:
    person_id = uuid.uuid4()
    first = _row(person_id=person_id)
    with pytest.raises(ValueError, match=r"2024.*two different values"):
        upsert_person_name_sources(None, [first, {**first, "full_name": "Y"}])  # type: ignore[arg-type]
    geography_id = uuid.uuid4()
    geo = _geo_row(geography_id=geography_id)
    with pytest.raises(ValueError, match=r"census\.tiger.*two different values"):
        upsert_geography_name_sources(None, [geo, {**geo, "name": "Y"}])  # type: ignore[arg-type]
    # Evidence that differs is a different value too.
    with pytest.raises(ValueError, match="two different values"):
        upsert_person_name_sources(None, [first, {**first, "artifact_id": uuid.uuid4()}])  # type: ignore[arg-type]


def test_gated_datasets_are_checked_and_ungated_ones_are_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only datasets in PERSON_JOIN_DATASETS reach require_person_join (it raises for an ungated dataset)."""
    gated = identitygate.PERSON_JOIN_DATASETS[0]
    calls: list[str] = []

    def record(dataset_id: str, inventory: Any = None) -> dict:
        calls.append(dataset_id)
        if dataset_id == gated:
            raise identitygate.PersonJoinBlocked(f"{dataset_id} blocked")
        return {}

    monkeypatch.setattr(identitygate, "require_person_join", record)
    with pytest.raises(identitygate.PersonJoinBlocked, match=gated):
        upsert_person_name_sources(None, [_row(dataset_id=gated), _row(dataset_id=OPENSTATES)])  # type: ignore[arg-type]
    assert calls == [gated]  # refused before any write (there was no cursor to write with)

    class Cursor:
        def execute(self, *args: Any) -> None:
            self.ran = True

        def fetchall(self) -> list:
            return []

    calls.clear()
    cursor = Cursor()
    for dataset in (OPENSTATES, LEGISLATORS, CONGRESS_GOV):
        assert upsert_person_name_sources(cursor, [_row(dataset_id=dataset)]) == {"inserted": 0, "updated": 0}  # type: ignore[arg-type]
    assert calls == [] and cursor.ran


def test_the_real_gate_refuses_a_blocked_dataset_today() -> None:
    blocked = [d for d in identitygate.PERSON_JOIN_DATASETS if identitygate.person_join(d)["state"] != "ready"]
    assert blocked, "every gated dataset is open: this guard now needs a fresh test"
    with pytest.raises(identitygate.PersonJoinBlocked):
        upsert_person_name_sources(None, [_row(dataset_id=blocked[0])])  # type: ignore[arg-type]


@pytest.mark.parametrize("document", [{}, [], {"version": 1}, {"version": 1, "person": {"kinds": None}},
                                       {"version": 1, "person": "x", "geography": 3}])
def test_sync_precedence_refuses_an_empty_or_malformed_document_before_touching_the_database(document: Any) -> None:
    """Called with an empty document it used to prune every ranking."""
    with pytest.raises(ValueError, match="precedence not synced"):
        sync_precedence(document)


def test_resolve_command_rejects_an_unknown_entity() -> None:
    result = CliRunner().invoke(app, ["resolve", "--entity", "organization"])
    assert result.exit_code != 0
    assert "person" in result.output and "geography" in result.output


def test_new_python_holds_no_long_sql() -> None:
    """Everything longer than a one-line lock lives in sql/query/ (Story 10.2 boundary)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "opendiscourse_research"
    for name in ("repositories/names.py", "precedence.py"):
        text = (root / name).read_text()
        for keyword in ("INSERT INTO", "DELETE FROM", "UPDATE core", "CREATE TABLE", "WITH "):
            assert keyword not in text, f"{name} embeds SQL ({keyword})"


# --------------------------------------------------------------------------- db fixtures


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
        container = postgres.PostgresContainer("postgis/postgis:17-3.5", username="test", password="test", dbname="test")
        container.start()
        settings.database_url = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://", 1)
    try:
        apply_migrations()
        sync_inventory()
        yield
    finally:
        _cleanup()
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


def _cleanup() -> None:
    """Remove every row these tests wrote, children before parents, and restore the file's precedence."""
    like = f"{PREFIX}-%"
    with connect() as conn:
        conn.execute("DELETE FROM ingest.person_merge WHERE exception_id LIKE %s", (like,))
        conn.execute("DELETE FROM core.person_identifier WHERE external_id LIKE %s", (like,))
        # Deleting the entity removes its assertions with it (ON DELETE CASCADE).
        conn.execute("DELETE FROM core.person WHERE metadata->>'names_test' = 'true'")
        conn.execute("DELETE FROM core.geography WHERE geoid LIKE %s", (like,))
        conn.execute("DELETE FROM ingest.artifact WHERE artifact_key LIKE %s", (like,))
        conn.execute("DELETE FROM ingest.raw_payload WHERE source_url LIKE %s", (f"https://{PREFIX}%",))
        conn.execute("DELETE FROM ingest.run WHERE parameters->>'names_test' = 'true'")
        conn.commit()
    sync_precedence()


@pytest.fixture
def warehouse(catalog_database: None) -> Iterator[None]:
    """A clean slate around each db test."""
    _cleanup()
    yield
    _cleanup()


# --------------------------------------------------------------------------- db helpers


def _run(dataset: str = OPENSTATES) -> uuid.UUID:
    run = IngestionRun(dataset, {"names_test": "true"}, mode="manual")
    with run:
        pass
    return run.run_id


def _artifact(dataset: str) -> uuid.UUID:
    with connect() as conn:
        artifact = conn.execute(
            "INSERT INTO ingest.artifact (dataset_id, remote_url, local_path, artifact_key, status) "
            "VALUES (%s, 'https://example.test', '/none', %s, 'planned') RETURNING artifact_id",
            (dataset, f"{PREFIX}-{uuid.uuid4().hex}"),
        ).fetchone()["artifact_id"]
        conn.commit()
    return artifact


def _payload(run_id: uuid.UUID) -> uuid.UUID:
    with connect() as conn:
        payload = conn.execute(
            "INSERT INTO ingest.raw_payload (run_id, source_url, checksum_sha256, payload) "
            "VALUES (%s, %s, %s, '{}') RETURNING payload_id",
            (run_id, f"https://{PREFIX}.test/{uuid.uuid4().hex}", uuid.uuid4().hex),
        ).fetchone()["payload_id"]
        conn.commit()
    return payload


def _person(name: str = "Placeholder Person", given: str | None = None, family: str | None = None) -> uuid.UUID:
    with connect() as conn:
        person = conn.execute(
            "INSERT INTO core.person (full_name, given_name, family_name, metadata) "
            "VALUES (%s, %s, %s, '{\"names_test\": true}') RETURNING person_id",
            (name, given, family),
        ).fetchone()["person_id"]
        conn.commit()
    return person


def _geography(geography_type: str = "county", name: str | None = None) -> uuid.UUID:
    with connect() as conn:
        geography = conn.execute(
            "INSERT INTO core.geography (geography_type, geoid, name) VALUES (%s, %s, %s) RETURNING geography_id",
            (geography_type, f"{PREFIX}-{next(_counter):04d}-{uuid.uuid4().hex[:6]}", name),
        ).fetchone()["geography_id"]
        conn.commit()
    return geography


def _say(person_id: uuid.UUID, kind: str, dataset: str, vintage: str, full: str, given: str | None = None,
         family: str | None = None, run_id: uuid.UUID | None = None, payload: bool = False) -> dict[str, int]:
    run_id = run_id or _run(dataset)
    row = {"person_id": person_id, "name_kind": kind, "full_name": full, "given_name": given, "family_name": family,
           "dataset_id": dataset, "source_vintage": vintage, "run_id": run_id,
           "artifact_id": None if payload else _artifact(dataset),
           "payload_id": _payload(run_id) if payload else None}
    with connect() as conn:
        result = upsert_person_name_sources(conn.cursor(), [row])
        conn.commit()
    return result


def _say_geo(geography_id: uuid.UUID, kind: str, dataset: str, vintage: str, name: str,
             run_id: uuid.UUID | None = None) -> dict[str, int]:
    run_id = run_id or _run(dataset)
    row = {"geography_id": geography_id, "name_kind": kind, "name": name, "dataset_id": dataset,
           "source_vintage": vintage, "run_id": run_id, "artifact_id": _artifact(dataset), "payload_id": None}
    with connect() as conn:
        result = upsert_geography_name_sources(conn.cursor(), [row])
        conn.commit()
    return result


def _resolve(entity: str = "person", dry_run: bool = False) -> dict[str, Any]:
    with connect() as conn:
        return resolve_names(conn, entity, dry_run=dry_run)


def _person_row(person_id: uuid.UUID) -> dict[str, Any]:
    with connect() as conn:
        return conn.execute("SELECT * FROM core.person WHERE person_id = %s", (person_id,)).fetchone()


def _geography_row(geography_id: uuid.UUID) -> dict[str, Any]:
    with connect() as conn:
        return conn.execute("SELECT * FROM core.geography WHERE geography_id = %s", (geography_id,)).fetchone()


def _source(table: str, source_id: uuid.UUID) -> dict[str, Any]:
    with connect() as conn:
        return conn.execute(
            f"SELECT * FROM core.{table} WHERE {table}_id = %s", (source_id,)  # noqa: S608 - fixed names
        ).fetchone()


def _ranked(person_display: list[str], **person_kinds: list[str]) -> dict[str, Any]:
    """The file's precedence with the person section replaced (geography untouched)."""
    document = copy.deepcopy(load_precedence())
    document["person"] = {
        "display": person_display,
        "kinds": {kind: [{"dataset": dataset, "field": "f"} for dataset in datasets]
                  for kind, datasets in person_kinds.items()},
    }
    return document


# --------------------------------------------------------------------------- db: schema


@db
def test_schema_has_assertion_tables_pointers_and_guards(warehouse: None) -> None:
    with connect() as conn:
        tables = {r["t"] for r in conn.execute(
            "SELECT format('%s.%s', schemaname, tablename) AS t FROM pg_tables "
            "WHERE tablename IN ('person_name_source', 'geography_name_source', 'attribute_precedence', 'name_display')"
        ).fetchall()}
        nulls_not_distinct = {r["relname"] for r in conn.execute(
            "SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid WHERE i.indnullsnotdistinct"
        ).fetchall()}
        pointers = {r["conrelid"] for r in conn.execute(
            "SELECT conrelid::regclass::text AS conrelid FROM pg_constraint WHERE contype = 'f' AND confrelid IN "
            "('core.person_name_source'::regclass, 'core.geography_name_source'::regclass)"
        ).fetchall()}
        triggers = {r["tgname"] for r in conn.execute(
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgname LIKE '%%_guard'"
        ).fetchall()}
    assert tables == {"core.person_name_source", "core.geography_name_source",
                      "catalog.attribute_precedence", "catalog.name_display"}
    assert {"person_name_source_key", "geography_name_source_key"} <= nulls_not_distinct
    assert {"core.person", "core.geography"} <= pointers  # name_source_id points at the winning assertion
    assert {"person_names_guard", "geography_name_guard"} <= triggers


@db
def test_an_assertion_needs_artifact_or_payload_and_a_run(warehouse: None) -> None:
    person = _person()
    run = _run()
    with connect() as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO core.person_name_source (person_id, name_kind, full_name, dataset_id, source_vintage, run_id) "
                "VALUES (%s, 'common', 'X', %s, '2024', %s)", (person, OPENSTATES, run))
    with connect() as conn:
        with pytest.raises(psycopg.errors.NotNullViolation):
            conn.execute(
                "INSERT INTO core.person_name_source (person_id, name_kind, full_name, dataset_id, source_vintage, "
                "artifact_id) VALUES (%s, 'common', 'X', %s, '2024', %s)", (person, OPENSTATES, _artifact(OPENSTATES)))
    with connect() as conn:  # a payload alone is evidence too (OpenStates and Congress.gov have no artifact)
        conn.execute(
            "INSERT INTO core.person_name_source (person_id, name_kind, full_name, dataset_id, source_vintage, "
            "payload_id, run_id) VALUES (%s, 'common', 'X', %s, '2024', %s, %s)",
            (person, OPENSTATES, _payload(run), run))
        conn.commit()


@db
def test_a_kind_outside_the_entity_is_refused(warehouse: None) -> None:
    person, geography = _person(), _geography()
    with pytest.raises(psycopg.errors.CheckViolation):
        _say(person, "short", OPENSTATES, "2024", "X")
    with pytest.raises(psycopg.errors.CheckViolation):
        _say_geo(geography, "official", TIGER, "2024", "X")


# --------------------------------------------------------------------------- db: assertion upserts


@db
def test_upsert_is_idempotent_and_moves_evidence_in_place(warehouse: None) -> None:
    person = _person()
    run = _run()
    first = _say(person, "common", OPENSTATES, "2024", "Mike Lawler", run_id=run)
    with connect() as conn:  # same evidence again: nothing inserted, nothing updated
        artifact = conn.execute("SELECT artifact_id FROM core.person_name_source WHERE person_id = %s",
                                (person,)).fetchone()["artifact_id"]
        again = upsert_person_name_sources(conn.cursor(), [{
            "person_id": person, "name_kind": "common", "full_name": "Mike Lawler", "given_name": None,
            "family_name": None, "dataset_id": OPENSTATES, "source_vintage": "2024", "run_id": run,
            "artifact_id": artifact, "payload_id": None}])
        conn.commit()
    assert first == {"inserted": 1, "updated": 0}
    assert again == {"inserted": 0, "updated": 0}
    # A rerun by a later run with a new artifact moves the evidence, and adds no assertion.
    moved = _say(person, "common", OPENSTATES, "2024", "Mike Lawler")
    corrected = _say(person, "common", OPENSTATES, "2024", "Michael Lawler", "Michael", "Lawler")
    assert moved == {"inserted": 0, "updated": 1} and corrected == {"inserted": 0, "updated": 1}
    with connect() as conn:
        rows = conn.execute("SELECT * FROM core.person_name_source WHERE person_id = %s", (person,)).fetchall()
    assert len(rows) == 1
    assert (rows[0]["full_name"], rows[0]["given_name"]) == ("Michael Lawler", "Michael")
    assert rows[0]["artifact_id"] != artifact and rows[0]["run_id"] != run


@db
def test_a_new_vintage_or_kind_is_a_new_assertion_and_the_geography_upsert_matches(warehouse: None) -> None:
    person, geography = _person(), _geography()
    assert _say(person, "common", OPENSTATES, "2024", "A")["inserted"] == 1
    assert _say(person, "common", OPENSTATES, "2025", "A")["inserted"] == 1
    assert _say(person, "official", OPENSTATES, "2024", "A")["inserted"] == 1
    assert _say_geo(geography, "short", TIGER, "2023", "Autauga")["inserted"] == 1
    assert _say_geo(geography, "short", TIGER, "2023", "Autauga")["updated"] == 1  # new run and artifact
    assert _say_geo(geography, "short", TIGER, "2024", "Autauga")["inserted"] == 1
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM core.person_name_source WHERE person_id = %s",
                            (person,)).fetchone()["n"] == 3
        assert conn.execute("SELECT count(*) AS n FROM core.geography_name_source WHERE geography_id = %s",
                            (geography,)).fetchone()["n"] == 2


# --------------------------------------------------------------------------- db: the precedence sync


@db
def test_precedence_sync_matches_the_file_and_a_rerun_writes_nothing(warehouse: None) -> None:
    document = load_precedence()
    assert sync_precedence(document) == {"display_written": 0, "ranks_written": 0, "ranks_removed": 0,
                                         "display_removed": 0}
    with connect() as conn:
        ranks = conn.execute("SELECT entity, name_kind, geography_type, rank, dataset_id, field "
                             "FROM catalog.attribute_precedence").fetchall()
        display = conn.execute("SELECT entity, name_kind, position FROM catalog.name_display").fetchall()
    assert {(r["entity"], r["name_kind"], r["geography_type"], r["rank"], r["dataset_id"], r["field"])
            for r in ranks} == {(e, k, t, r, d, f) for e, k, t, r, d, f in _entries(document)}
    assert {(r["entity"], r["name_kind"], r["position"]) for r in display} == set(_display(document))


@db
def test_precedence_sync_removes_dropped_rows_and_survives_a_reordering(warehouse: None) -> None:
    swapped = _ranked(["common", "official"], common=[OPENSTATES],
                      official=[OPENSTATES, CONGRESS_GOV, LEGISLATORS])  # ranks 1 and 3 change places
    counts = sync_precedence(swapped)
    # Field text differs on the four replaced rows. Roster, voteview, and the four
    # legislator name parts are ranked but not in this replacement, so those six are removed.
    assert counts["ranks_written"] == 4 and counts["ranks_removed"] == 6
    with connect() as conn:
        order = [r["dataset_id"] for r in conn.execute(
            "SELECT dataset_id FROM catalog.attribute_precedence WHERE entity = 'person' AND name_kind = 'official' "
            "ORDER BY rank").fetchall()]
    assert order == [OPENSTATES, CONGRESS_GOV, LEGISLATORS]
    dropped = _ranked(["common"], common=[OPENSTATES])
    counts = sync_precedence(dropped)
    assert counts["ranks_removed"] == 3 and counts["display_removed"] == 1
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM catalog.attribute_precedence WHERE entity = 'person' "
                            "AND name_kind = 'official'").fetchone()["n"] == 0
    sync_precedence()  # back to the file
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM catalog.attribute_precedence WHERE entity = 'person' "
                            "AND name_kind = 'official'").fetchone()["n"] == 3


# --------------------------------------------------------------------------- db: the resolver


@db
def test_higher_rank_wins_and_the_triple_travels_from_one_assertion(warehouse: None) -> None:
    """Matrix: rank wins; a given/family/full triple comes from one assertion, never a mix."""
    sync_precedence(_ranked(["official"], official=[LEGISLATORS, OPENSTATES]))
    person = _person("Placeholder")
    _say(person, "official", OPENSTATES, "2024", "Mike Lawler", "Mike", "Lawler")
    _say(person, "official", LEGISLATORS, "2024", "Michael Lawler", None, "Lawler-Official")
    result = _resolve()
    assert result["changed"] == 1
    row = _person_row(person)
    assert (row["full_name"], row["given_name"], row["family_name"]) == ("Michael Lawler", None, "Lawler-Official")
    won = _source("person_name_source", row["name_source_id"])
    assert (won["dataset_id"], won["name_kind"]) == (LEGISLATORS, "official")
    # Flipping the file flips the winner, and only the file: the other assertion was kept.
    sync_precedence(_ranked(["official"], official=[OPENSTATES, LEGISLATORS]))
    assert _resolve()["changed"] == 1
    flipped = _person_row(person)
    assert (flipped["full_name"], flipped["given_name"], flipped["family_name"]) == ("Mike Lawler", "Mike", "Lawler")
    assert _source("person_name_source", flipped["name_source_id"])["dataset_id"] == OPENSTATES


@db
def test_the_shipped_file_shows_the_common_name_and_falls_back_to_official(warehouse: None) -> None:
    both, official_only = _person("x"), _person("y")
    _say(both, "official", LEGISLATORS, "2024", "Michael Lawler", "Michael", "Lawler")
    _say(both, "common", OPENSTATES, "2024", "Mike Lawler", "Mike", "Lawler")
    _say(official_only, "official", LEGISLATORS, "2024", "Only Official")
    assert _resolve()["changed"] == 2
    assert _person_row(both)["full_name"] == "Mike Lawler"
    assert _source("person_name_source", _person_row(both)["name_source_id"])["name_kind"] == "common"
    assert _person_row(official_only)["full_name"] == "Only Official"


@db
def test_a_roster_name_does_not_block_resolve_or_change_the_shown_name(warehouse: None) -> None:
    """A committee roster is ranked and not displayed. Resolve still runs."""
    person = _person("Placeholder")
    _say(person, "common", OPENSTATES, "2024", "Mike Lawler", "Mike", "Lawler")
    _say(person, "roster", "congress.committee_membership", "2026-09-03", "Printed Mike")
    assert _resolve()["changed"] == 1
    row = _person_row(person)
    assert row["full_name"] == "Mike Lawler"
    assert _source("person_name_source", row["name_source_id"])["name_kind"] == "common"


@db
def test_equal_rank_takes_the_newer_vintage(warehouse: None) -> None:
    """Matrix: same dataset, two vintages."""
    geography = _geography("county")
    _say_geo(geography, "short", TIGER, "2023", "Old Name")
    _say_geo(geography, "short", TIGER, "2024", "New Name")
    _say_geo(geography, "short", TIGER, "2022-09", "Older Name")
    _resolve("geography")
    row = _geography_row(geography)
    assert row["name"] == "New Name"
    assert _source("geography_name_source", row["name_source_id"])["source_vintage"] == "2024"


@db
def test_the_result_does_not_depend_on_insertion_order(warehouse: None) -> None:
    """Matrix: order independence, for people and for geographies."""
    sync_precedence(_ranked(["official", "common"], official=[LEGISLATORS, OPENSTATES], common=[OPENSTATES]))
    people = [("official", LEGISLATORS, "2020", "Leg 2020", "L", "P"), ("official", OPENSTATES, "2024", "OS 2024", "O", "S"),
              ("official", LEGISLATORS, "2024", "Leg 2024", "L4", "P4"), ("common", OPENSTATES, "2023", "Common 2023", "C", "N")]
    geos = [("short", TIGER, "2023", "T23"), ("short", TIGER, "2024", "T24"), ("full", PEP, "2025", "Full PEP")]
    winners: set[tuple] = set()
    geo_winners: set[tuple] = set()
    for order in itertools.permutations(range(4)):
        person = _person(f"p{order}")
        for index in order:
            _say(person, *people[index])
    for order in itertools.permutations(range(3)):
        geography = _geography("county")
        for index in order:
            _say_geo(geography, *geos[index])
    _resolve()
    _resolve("geography")
    with connect() as conn:
        for row in conn.execute("SELECT p.full_name, p.given_name, p.family_name, s.dataset_id, s.name_kind, "
                                "s.source_vintage FROM core.person p JOIN core.person_name_source s "
                                "ON s.person_name_source_id = p.name_source_id "
                                "WHERE p.metadata->>'names_test' = 'true'").fetchall():
            winners.add(tuple(row.values()))
        for row in conn.execute("SELECT g.name, s.dataset_id, s.name_kind, s.source_vintage FROM core.geography g "
                                "JOIN core.geography_name_source s ON s.geography_name_source_id = g.name_source_id "
                                "WHERE g.geoid LIKE %s", (f"{PREFIX}-%",)).fetchall():
            geo_winners.add(tuple(row.values()))
    assert winners == {("Leg 2024", "L4", "P4", LEGISLATORS, "official", "2024")}
    assert geo_winners == {("T24", TIGER, "short", "2024")}


@db
def test_kind_fallback_never_leaves_a_name_null(warehouse: None) -> None:
    """Matrix: display [short, full] with only `full` asserted shows `full`."""
    county = _geography("county")
    _say_geo(county, "full", PEP, "2024", "Autauga County")
    _resolve("geography")
    assert _geography_row(county)["name"] == "Autauga County"
    _say_geo(county, "short", TIGER, "2024", "Autauga")  # the better kind arrives later and takes over
    _resolve("geography")
    assert _geography_row(county)["name"] == "Autauga"


@db
def test_geography_rank_is_per_type(warehouse: None) -> None:
    county, cbsa, state = _geography("county"), _geography("cbsa"), _geography("state")
    for geography in (county,):
        _say_geo(geography, "full", ACS, "2023", "Autauga County, Alabama")
        _say_geo(geography, "full", PEP, "2023", "Autauga County")
        _say_geo(geography, "full", TIGER, "2023", "Autauga County (lsad)")
    _say_geo(cbsa, "full", TIGER, "2023", "Abilene, TX Metro Area")
    _say_geo(state, "full", ACS, "2023", "Alabama (acs)")
    _say_geo(state, "full", PEP, "2023", "Alabama")
    _resolve("geography")
    assert _geography_row(county)["name"] == "Autauga County (lsad)"  # county: TIGER > PEP > ACS
    assert _geography_row(cbsa)["name"] == "Abilene, TX Metro Area"
    assert _geography_row(state)["name"] == "Alabama"  # state: PEP > ACS (TIGER is not ranked for state full)


@db
def test_a_row_with_no_assertion_is_untouched_and_a_rerun_changes_nothing(warehouse: None) -> None:
    """Matrix: no assertion; rerun."""
    bare = _person("Bare Person", "Bare", "Person")
    asserted = _person("Placeholder")
    unnamed = _geography("county")
    named = _geography("county", "Legacy Name")
    _say(asserted, "official", LEGISLATORS, "2024", "Real Name")
    _say_geo(named, "short", TIGER, "2024", "Tiger Name")
    assert (_resolve()["changed"], _resolve("geography")["changed"]) == (1, 1)
    row = _person_row(bare)
    assert (row["full_name"], row["given_name"], row["family_name"], row["name_source_id"]) == (
        "Bare Person", "Bare", "Person", None)
    assert _geography_row(unnamed)["name"] is None and _geography_row(unnamed)["name_source_id"] is None
    before = (_person_row(asserted), _geography_row(named))
    assert (_resolve()["changed"], _resolve("geography")["changed"]) == (0, 0)
    assert (_person_row(asserted), _geography_row(named)) == before


@db
def test_dry_run_reports_old_and_new_values_and_writes_nothing(warehouse: None) -> None:
    person, geography = _person("Old Name", "Old", "Name"), _geography("county", "Old Geo")
    _say(person, "official", LEGISLATORS, "2024", "New Name", "New", "Name")
    _say_geo(geography, "short", TIGER, "2024", "New Geo")
    result = _resolve("person", dry_run=True)
    [change] = result["rows"]
    assert result["dry_run"] is True and result["changed"] == 1
    assert (change["person_id"], change["old_full_name"], change["full_name"]) == (person, "Old Name", "New Name")
    assert (change["old_given_name"], change["given_name"]) == ("Old", "New")
    assert change["old_name_source_id"] is None and change["name_source_id"] is not None
    [geo_change] = _resolve("geography", dry_run=True)["rows"]
    assert (geo_change["old_name"], geo_change["name"]) == ("Old Geo", "New Geo")
    assert _person_row(person)["full_name"] == "Old Name" and _person_row(person)["name_source_id"] is None
    assert _geography_row(geography)["name"] == "Old Geo"
    assert _resolve()["rows"][0]["person_id"] == person  # the same change applies for real afterwards
    assert _person_row(person)["full_name"] == "New Name"


@db
def test_an_unranked_dataset_kind_or_type_fails_and_names_itself(warehouse: None) -> None:
    """Matrix: unranked dataset; also kind and geography type, and nothing is written on failure."""
    person, geography = _person("Keep Me"), _geography("county", "Keep Geo")
    _say(person, "official", ACS, "2024", "Wrong Source")  # ACS has no person ranking at all
    with pytest.raises(UnrankedSource, match=r"dataset 'census\.acs_5'"):
        _resolve()
    assert _person_row(person)["full_name"] == "Keep Me"
    _say(person, "official", LEGISLATORS, "2024", "Ranked Source")
    with pytest.raises(UnrankedSource, match=r"census\.acs_5"):  # one bad assertion still blocks the rest
        _resolve()

    other = _geography("place")
    _say_geo(other, "short", TIGER, "2024", "A Place")
    with pytest.raises(UnrankedSource, match=r"geography type 'place'"):
        _resolve("geography")
    state = _geography("state")
    _say_geo(state, "short", PEP, "2024", "Alabama")  # PEP is ranked for state, but only for `full`
    with pytest.raises(UnrankedSource, match=r"no precedence row for geography name kind 'short'.*'state'"):
        _resolve("geography")
    assert _geography_row(geography)["name"] == "Keep Geo"

    sync_precedence(_ranked(["common"], common=[OPENSTATES]))  # official is no longer ranked or displayed
    _say(_person("x"), "official", OPENSTATES, "2024", "Kind Gone")
    with pytest.raises(UnrankedSource, match=r"person name kind 'official'"):
        _resolve()


@db
def test_precedence_gap_after_the_file_drops_a_dataset_fails_closed(warehouse: None) -> None:
    person = _person("x")
    _say(person, "official", LEGISLATORS, "2024", "Was Ranked")
    _resolve()
    sync_precedence(_ranked(["official"], official=[OPENSTATES]))  # legislators dropped from the file
    with pytest.raises(UnrankedSource, match=r"dataset 'congress\.legislators'"):
        _resolve()


# --------------------------------------------------------------------------- db: the write guard


@db
def test_a_resolved_name_cannot_be_written_directly(warehouse: None) -> None:
    """Matrix: direct write to a row with a pointer is refused (42501); the resolver passes."""
    person, geography = _person("Placeholder"), _geography("county")
    _say(person, "official", LEGISLATORS, "2024", "Resolved Name", "Resolved", "Name")
    _say_geo(geography, "short", TIGER, "2024", "Resolved Geo")
    _resolve()
    _resolve("geography")
    pointer = _person_row(person)["name_source_id"]
    attempts = [
        ("UPDATE core.person SET full_name = 'Hacked' WHERE person_id = %s", person),
        ("UPDATE core.person SET given_name = NULL WHERE person_id = %s", person),
        ("UPDATE core.person SET family_name = 'X' WHERE person_id = %s", person),
        ("UPDATE core.person SET name_source_id = NULL WHERE person_id = %s", person),
        ("UPDATE core.geography SET name = 'Hacked' WHERE geography_id = %s", geography),
        ("UPDATE core.geography SET name_source_id = NULL WHERE geography_id = %s", geography),
    ]
    for statement, key in attempts:
        with connect() as conn, pytest.raises(psycopg.errors.InsufficientPrivilege) as caught:
            conn.execute(statement, (key,))
        assert caught.value.sqlstate == "42501"
    assert "research-db resolve" in str(caught.value)
    assert _person_row(person)["full_name"] == "Resolved Name" and _person_row(person)["name_source_id"] == pointer
    with connect() as conn:  # everything else about the row stays writable, and a no-op name write is not a change
        conn.execute("UPDATE core.person SET metadata = metadata || '{\"note\": 1}' WHERE person_id = %s", (person,))
        conn.execute("UPDATE core.person SET full_name = full_name WHERE person_id = %s", (person,))
        conn.execute("UPDATE core.geography SET parent_geoid = 'x' WHERE geography_id = %s", (geography,))
        conn.commit()


@db
def test_an_unresolved_row_is_written_as_before_and_cannot_be_pointed_by_hand(warehouse: None) -> None:
    person, geography = _person("Before"), _geography("county")
    with connect() as conn:
        conn.execute("UPDATE core.person SET full_name = 'After', given_name = 'A' WHERE person_id = %s", (person,))
        conn.execute("UPDATE core.geography SET name = 'After Geo' WHERE geography_id = %s", (geography,))
        conn.commit()
    assert _person_row(person)["full_name"] == "After" and _geography_row(geography)["name"] == "After Geo"
    _say(person, "official", LEGISLATORS, "2024", "X")
    with connect() as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("UPDATE core.person SET name_source_id = %s WHERE person_id = %s", (_assertion_id(person), person))


def _assertion_id(person_id: uuid.UUID) -> uuid.UUID:
    with connect() as conn:
        return conn.execute("SELECT person_name_source_id AS i FROM core.person_name_source WHERE person_id = %s",
                            (person_id,)).fetchone()["i"]


@db
def test_the_resolver_flag_does_not_outlive_its_transaction(warehouse: None) -> None:
    person = _person("Before")
    _say(person, "official", LEGISLATORS, "2024", "Resolved")
    with connect() as conn:
        with conn.transaction():
            cur = conn.cursor()
            apply_resolution(cur, "person")
            cur.execute("SELECT current_setting('opendiscourse.resolver', true) AS flag")
            assert cur.fetchone()["flag"] in ("", None)
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                cur.execute("UPDATE core.person SET full_name = 'Hacked' WHERE person_id = %s", (person,))
    assert _person_row(person)["full_name"] == "Resolved"


@db
def test_deleting_a_resolved_person_removes_its_assertions_with_it(warehouse: None) -> None:
    person = _person("x")
    _say(person, "official", LEGISLATORS, "2024", "Gone")
    _resolve()
    with connect() as conn:
        conn.execute("DELETE FROM core.person WHERE person_id = %s", (person,))
        assert conn.execute("SELECT count(*) AS n FROM core.person_name_source WHERE person_id = %s",
                            (person,)).fetchone()["n"] == 0
        conn.commit()


# --------------------------------------------------------------------------- db: concurrency


@db
def test_two_resolvers_serialise_and_the_second_sees_nothing_left(warehouse: None) -> None:
    """Matrix: the second starts while the first holds the lock, waits, then reports zero changes."""
    person = _person("Placeholder")
    _say(person, "official", LEGISLATORS, "2024", "Resolved Once")
    outcome: dict[str, Any] = {}

    def second() -> None:
        with connect() as conn:
            outcome["result"] = resolve_names(conn, "person")

    with connect() as holder:
        with holder.transaction():
            cur = holder.cursor()
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended('resolve:person', 0))")
            first_changes = apply_resolution(cur, "person")
            thread = threading.Thread(target=second)
            thread.start()
            deadline = time.monotonic() + 10
            waiting = 0
            while not waiting and time.monotonic() < deadline:
                waiting = cur.execute(
                    "SELECT count(*) AS n FROM pg_locks WHERE locktype = 'advisory' AND NOT granted"
                ).fetchone()["n"]
                time.sleep(0.05)
            assert waiting == 1 and thread.is_alive() and "result" not in outcome  # the second waits
    thread.join(timeout=15)
    assert not thread.is_alive()
    assert len(first_changes) == 1 and outcome["result"]["changed"] == 0
    assert _person_row(person)["full_name"] == "Resolved Once"


# --------------------------------------------------------------------------- db: merge


@db
def test_merge_repoints_name_assertions_and_counts_the_ones_it_drops(warehouse: None) -> None:
    """Matrix: survivor's assertion with the same key is kept, the duplicate's dropped and counted."""
    survivor, duplicate = _person("Survivor"), _person("Duplicate")
    keys = (f"{PREFIX}-{uuid.uuid4().hex[:8]}", f"{PREFIX}-{uuid.uuid4().hex[:8]}")
    with connect() as conn:
        for person, key in zip((survivor, duplicate), keys, strict=True):
            conn.execute("INSERT INTO core.person_identifier (person_id, namespace, external_id) "
                         "VALUES (%s, 'fec', %s)", (person, key))
        conn.commit()
    _say(survivor, "common", OPENSTATES, "2024", "Survivor Common")
    _say(duplicate, "common", OPENSTATES, "2024", "Duplicate Common")  # same key: dropped
    _say(duplicate, "official", LEGISLATORS, "2024", "Duplicate Official")  # moves
    _say(duplicate, "common", OPENSTATES, "2025", "Duplicate Newer")  # moves
    _resolve()
    assert _person_row(duplicate)["name_source_id"] is not None  # the pointer is to an assertion that goes
    exception = SamePerson(f"{PREFIX}-merge", ("fec", keys[0]), ("fec", keys[1]))
    with connect() as conn:
        result = merge_person(conn, exception)
        conn.commit()
    assert result["status"] == "merged"
    assert result["counts"]["core.person_name_source"] == 2
    assert result["counts"]["person_name_source_dropped"] == 1
    with connect() as conn:
        rows = conn.execute("SELECT name_kind, dataset_id, source_vintage, full_name FROM core.person_name_source "
                            "WHERE person_id = %s ORDER BY name_kind, source_vintage", (survivor,)).fetchall()
        assert conn.execute("SELECT count(*) AS n FROM core.person WHERE person_id = %s", (duplicate,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM core.person_name_source WHERE full_name = 'Duplicate Common'"
                            ).fetchone()["n"] == 0
    assert [(r["name_kind"], r["source_vintage"], r["full_name"]) for r in rows] == [
        ("common", "2024", "Survivor Common"), ("common", "2025", "Duplicate Newer"),
        ("official", "2024", "Duplicate Official")]
    assert _resolve()["changed"] == 1  # the survivor now shows the newer common name
    assert _person_row(survivor)["full_name"] == "Duplicate Newer"
    assert "core.person_name_source" in PERSON_REFERENCES


# --------------------------------------------------------------------------- db: CLI and migration


@db
def test_cli_resolve_dry_run_then_apply_then_rerun(warehouse: None) -> None:
    person = _person("Placeholder")
    _say(person, "official", LEGISLATORS, "2024", "Cli Name")
    runner = CliRunner()
    dry = runner.invoke(app, ["resolve", "--dry-run", "--entity", "person"])
    assert dry.exit_code == 0, dry.output
    report = json.loads(dry.stdout)
    assert report["dry_run"] is True and report["resolved"][0]["changed"] == 1
    assert _person_row(person)["full_name"] == "Placeholder"
    applied = json.loads(runner.invoke(app, ["resolve"]).stdout)
    assert [r["entity"] for r in applied["resolved"]] == ["person", "geography"]
    assert applied["resolved"][0]["changed"] == 1 and applied["resolved"][1]["changed"] == 0
    assert _person_row(person)["full_name"] == "Cli Name"
    rerun = json.loads(runner.invoke(app, ["resolve"]).stdout)
    assert [r["changed"] for r in rerun["resolved"]] == [0, 0]


@db
def test_cli_resolve_fails_naming_the_unranked_source(warehouse: None) -> None:
    _say(_person("x"), "official", ACS, "2024", "Wrong")
    result = CliRunner().invoke(app, ["resolve"])
    assert result.exit_code == 1
    assert "census.acs_5" in result.output and "precedence.yaml" in result.output


@db
def test_downgrade_refuses_while_assertions_exist(warehouse: None) -> None:
    person = _person("x")
    _say(person, "official", LEGISLATORS, "2024", "Evidence")
    with pytest.raises(RuntimeError, match=r"core\.person_name_source holds 1 rows"):
        command.downgrade(_alembic_config(), "a4d9e1c7b356")
    with connect() as conn:  # nothing was dropped
        assert conn.execute("SELECT to_regclass('core.person_name_source') AS t").fetchone()["t"] is not None
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "c9e4a1b27d83"


@db
def test_migrating_populated_rows_changes_none_and_points_none(warehouse: None) -> None:
    """Downgrade, add people and geographies with distinct names, upgrade: every row is identical, no pointer."""
    config = _alembic_config()
    person_columns = "person_id, full_name, given_name, family_name, metadata"
    geography_columns = "geography_id, geography_type, geoid, name, parent_geoid, state_fips, county_fips, metadata"
    command.downgrade(config, "a4d9e1c7b356")
    try:
        with connect() as conn:
            for index in range(3):
                conn.execute("INSERT INTO core.person (full_name, given_name, family_name, metadata) "
                             "VALUES (%s, %s, %s, '{\"names_test\": true}')",
                             (f"Migrated Person {index}", f"Given {index}", None if index == 1 else f"Family {index}"))
                conn.execute("INSERT INTO core.geography (geography_type, geoid, name, state_fips) "
                             "VALUES ('county', %s, %s, '01')",
                             (f"{PREFIX}-mig-{index}", None if index == 2 else f"Migrated County {index}"))
            conn.commit()
            people = conn.execute(f"SELECT {person_columns} FROM core.person WHERE metadata->>'names_test' = 'true' "
                                  "ORDER BY person_id").fetchall()
            geographies = conn.execute(f"SELECT {geography_columns} FROM core.geography WHERE geoid LIKE %s "
                                       "ORDER BY geography_id", (f"{PREFIX}-mig-%",)).fetchall()
    finally:
        command.upgrade(config, "head")
    assert len(people) == 3 and len(geographies) == 3
    with connect() as conn:
        assert conn.execute(f"SELECT {person_columns} FROM core.person WHERE metadata->>'names_test' = 'true' "
                            "ORDER BY person_id").fetchall() == people
        assert conn.execute(f"SELECT {geography_columns} FROM core.geography WHERE geoid LIKE %s "
                            "ORDER BY geography_id", (f"{PREFIX}-mig-%",)).fetchall() == geographies
        assert conn.execute("SELECT count(*) AS n FROM core.person WHERE name_source_id IS NOT NULL").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM core.geography WHERE name_source_id IS NOT NULL"
                            ).fetchone()["n"] == 0
    assert _resolve()["changed"] == 0 and _resolve("geography")["changed"] == 0  # nothing asserted, nothing moves
    assert precedence_differs() is not None  # the upgrade left the catalog empty until the file is synced
    sync_precedence()


@db
def test_the_database_refuses_blank_names_and_bad_vintages_and_indexes_the_pointers(warehouse: None) -> None:
    person, geography, run = _person(), _geography(), _run()
    artifact = _artifact(OPENSTATES)
    for full in ("", "   "):
        with connect() as conn, pytest.raises(psycopg.errors.CheckViolation, match="name_check"):
            conn.execute("INSERT INTO core.person_name_source (person_id, name_kind, full_name, dataset_id, "
                         "source_vintage, artifact_id, run_id) VALUES (%s, 'common', %s, %s, '2024', %s, %s)",
                         (person, full, OPENSTATES, artifact, run))
    with connect() as conn, pytest.raises(psycopg.errors.CheckViolation, match="name_check"):
        conn.execute("INSERT INTO core.geography_name_source (geography_id, name_kind, name, dataset_id, "
                     "source_vintage, artifact_id, run_id) VALUES (%s, 'short', ' ', %s, '2024', %s, %s)",
                     (geography, TIGER, artifact, run))
    for vintage in ("2024-9", "24", "", "2024-09-1"):
        with connect() as conn, pytest.raises(psycopg.errors.CheckViolation, match="vintage_check"):
            conn.execute("INSERT INTO core.person_name_source (person_id, name_kind, full_name, dataset_id, "
                         "source_vintage, artifact_id, run_id) VALUES (%s, 'common', 'X', %s, %s, %s, %s)",
                         (person, OPENSTATES, vintage, artifact, run))
        with connect() as conn, pytest.raises(psycopg.errors.CheckViolation, match="vintage_check"):
            conn.execute("INSERT INTO core.geography_name_source (geography_id, name_kind, name, dataset_id, "
                         "source_vintage, artifact_id, run_id) VALUES (%s, 'short', 'X', %s, %s, %s, %s)",
                         (geography, TIGER, vintage, artifact, run))
    with connect() as conn:  # the three ISO shapes are fine
        for vintage in ("2024", "2024-09", "2024-09-01"):
            conn.execute("INSERT INTO core.person_name_source (person_id, name_kind, full_name, dataset_id, "
                         "source_vintage, artifact_id, run_id) VALUES (%s, 'common', 'X', %s, %s, %s, %s)",
                         (person, OPENSTATES, vintage, artifact, run))
        conn.commit()
        indexes = {r["indexname"]: r["indexdef"] for r in conn.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE indexname LIKE '%_name_source_pointer_idx'").fetchall()}
    assert set(indexes) == {"person_name_source_pointer_idx", "geography_name_source_pointer_idx"}
    assert all("WHERE (name_source_id IS NOT NULL)" in definition for definition in indexes.values())


@db
def test_a_same_value_duplicate_in_one_batch_stores_one_row(warehouse: None) -> None:
    person, geography, run = _person(), _geography(), _run()
    artifact = _artifact(OPENSTATES)
    person_row = {"person_id": person, "name_kind": "common", "full_name": "Twice", "given_name": None,
                  "family_name": None, "dataset_id": OPENSTATES, "source_vintage": "2024",
                  "artifact_id": artifact, "payload_id": None, "run_id": run}
    geo_row = {"geography_id": geography, "name_kind": "short", "name": "Twice", "dataset_id": TIGER,
               "source_vintage": "2024", "artifact_id": artifact, "payload_id": None, "run_id": run}
    with connect() as conn:
        assert upsert_person_name_sources(conn.cursor(), [person_row, dict(person_row)]) == {"inserted": 1, "updated": 0}
        assert upsert_geography_name_sources(conn.cursor(), [geo_row, dict(geo_row)]) == {"inserted": 1, "updated": 0}
        conn.commit()
        assert conn.execute("SELECT count(*) AS n FROM core.person_name_source WHERE person_id = %s",
                            (person,)).fetchone()["n"] == 1
        assert conn.execute("SELECT count(*) AS n FROM core.geography_name_source WHERE geography_id = %s",
                            (geography,)).fetchone()["n"] == 1


@db
def test_sync_precedence_dry_run_returns_the_counts_and_writes_nothing(warehouse: None) -> None:
    dropped = _ranked(["common"], common=[OPENSTATES])
    preview = sync_precedence(dropped, dry_run=True)
    # Official's three ranks, plus roster, voteview, and the four legislator name parts.
    assert preview["ranks_removed"] == 9 and preview["display_removed"] == 1
    with connect() as conn:
        assert conn.execute("SELECT count(*) AS n FROM catalog.attribute_precedence WHERE entity = 'person' "
                            "AND name_kind = 'official'").fetchone()["n"] == 3
    assert sync_precedence(dropped) == preview  # the real run reports the same counts
    sync_precedence()


@db
def test_resolve_refuses_to_run_on_a_stale_catalog(warehouse: None) -> None:
    """Drift: the file was edited (or the catalog was) and init-db has not run."""
    person = _person("Placeholder")
    _say(person, "official", LEGISLATORS, "2024", "Fresh")
    assert precedence_differs() is None
    runner = CliRunner()
    sync_precedence(_ranked(["official"], official=[OPENSTATES, LEGISLATORS]))  # the catalog now disagrees with the file
    assert precedence_differs() is not None
    result = runner.invoke(app, ["resolve", "--dry-run"])
    assert result.exit_code == 1
    assert "precedence.yaml differs from the catalog" in result.output and "init-db" in result.output
    assert _person_row(person)["full_name"] == "Placeholder"
    sync_precedence()  # in sync again: resolve runs
    ok = runner.invoke(app, ["resolve", "--dry-run", "--entity", "person"])
    assert ok.exit_code == 0 and json.loads(ok.stdout)["resolved"][0]["changed"] == 1


@db
def test_a_failed_second_entity_still_shows_the_first_result(warehouse: None) -> None:
    person = _person("Placeholder")
    _say(person, "official", LEGISLATORS, "2024", "Committed Name")
    _say_geo(_geography("place"), "short", TIGER, "2024", "Unranked Type")
    result = CliRunner().invoke(app, ["resolve"])
    assert result.exit_code == 1
    report = json.loads(result.stdout)  # stdout is the JSON only; the error goes to stderr
    assert [r["entity"] for r in report["resolved"]] == ["person"] and report["resolved"][0]["changed"] == 1
    assert "geography type 'place'" in result.output
    assert _person_row(person)["full_name"] == "Committed Name"  # the first entity did commit
