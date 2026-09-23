"""Story 10.1 database contract: person identity does not depend on load order (ADR-0005)."""

from __future__ import annotations

import itertools
import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, connect
from opendiscourse_research.identity_merge import (
    SamePerson,
    linked_identifiers,
    load_same_person,
)
from opendiscourse_research.ingestion.base import IngestionRun
from opendiscourse_research.repositories.legislation import (
    sync_openstates_federal_people,
    upsert_congress_person,
)
from opendiscourse_research.repositories.people import (
    PERSON_REFERENCES,
    merge_person,
    promote_legislators,
    resolve_person,
)

pytestmark = pytest.mark.db

PREFIX = "zztest-identity"
_counter = itertools.count(1)
_RUN = uuid.uuid4().hex[:6]


def _ids(n: int = 1) -> list[str]:
    return [f"{PREFIX}-{_RUN}-{next(_counter):04d}" for _ in range(n)]


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
        _cleanup()
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


def _cleanup() -> None:
    """Remove every row these tests wrote, children before parents (the DB is shared)."""
    like = f"{PREFIX}-%"
    with connect() as conn:
        conn.execute("DELETE FROM ingest.person_merge_vote WHERE person_merge_id IN "
                     "(SELECT person_merge_id FROM ingest.person_merge WHERE exception_id LIKE %s)", (like,))
        conn.execute("DELETE FROM ingest.person_merge WHERE exception_id LIKE %s", (like,))
        conn.execute("DELETE FROM ingest.identity_conflict WHERE subject LIKE %s", (f"%{PREFIX}-%",))
        conn.execute(
            "DELETE FROM fact.member_vote WHERE person_id IN (SELECT person_id FROM core.person "
            "WHERE metadata->>'identity_test' = 'true')"
        )
        conn.execute(
            "DELETE FROM core.bill_sponsorship WHERE person_id IN (SELECT person_id FROM core.person "
            "WHERE metadata->>'identity_test' = 'true')"
        )
        conn.execute(
            "DELETE FROM core.committee_assignment WHERE person_id IN "
            "(SELECT person_id FROM core.person WHERE metadata->>'identity_test' = 'true') "
            "OR bioguide LIKE %s",
            (like,),
        )
        conn.execute("DELETE FROM core.committee WHERE thomas_key LIKE %s", (like,))
        conn.execute(
            "DELETE FROM core.membership WHERE person_id IN (SELECT person_id FROM core.person "
            "WHERE metadata->>'identity_test' = 'true')"
        )
        conn.execute(
            "DELETE FROM fact.member_vote WHERE roll_call_id IN "
            "(SELECT roll_call_id FROM core.roll_call WHERE jurisdiction = %s)", (f"{PREFIX}-jurisdiction",)
        )
        conn.execute("DELETE FROM core.roll_call WHERE jurisdiction = %s", (f"{PREFIX}-jurisdiction",))
        conn.execute("DELETE FROM core.person_identifier WHERE external_id LIKE %s", (like,))
        conn.execute("DELETE FROM core.person WHERE metadata->>'identity_test' = 'true'")
        # Loader-made people carry the loader's metadata; ours are the ones with these names
        # and no identifier left (their identifiers were deleted above).
        conn.execute(
            "DELETE FROM core.person p WHERE p.full_name IN ('Legis Person', 'Common Name', 'Common', 'State Only') "
            "AND NOT EXISTS (SELECT 1 FROM core.person_identifier i WHERE i.person_id = p.person_id) "
            "AND NOT EXISTS (SELECT 1 FROM core.membership m WHERE m.person_id = p.person_id)"
        )
        conn.execute("DELETE FROM ingest.artifact WHERE artifact_key LIKE %s", (like,))
        conn.execute("DELETE FROM ingest.run WHERE parameters->>'identity_test' = 'true'")
        conn.commit()
    _drop_fake_openstates()


def _new(name: str) -> dict:
    return {"full_name": name, "given_name": None, "family_name": None, "metadata": {"identity_test": True}}


def _resolve(identifiers, dataset="congress.legislators", **kw):
    with connect() as conn:
        cur = conn.cursor()
        result = resolve_person(
            cur, identifiers, dataset_id=dataset, subject=f"test:{identifiers[0][1]}",
            new_person=_new("T"), exceptions=kw.pop("exceptions", []), **kw,
        )
        conn.commit()
    return result


def _owner(namespace: str, external_id: str):
    with connect() as conn:
        row = conn.execute(
            "SELECT person_id FROM core.person_identifier WHERE namespace = %s AND external_id = %s",
            (namespace, external_id),
        ).fetchone()
    return row["person_id"] if row else None


def _identifiers_of(person_id) -> set[tuple[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT namespace, external_id FROM core.person_identifier WHERE person_id = %s", (person_id,)
        ).fetchall()
    return {(r["namespace"], r["external_id"]) for r in rows}


def _conflicts(kind: str | None = None):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM ingest.identity_conflict WHERE subject LIKE %s AND (%s::text IS NULL OR kind = %s)",
            (f"%{PREFIX}-%", kind, kind),
        ).fetchall()


def _run_and_artifact():
    """A real run and artifact so staged legislator rows satisfy their foreign keys."""
    run = IngestionRun("congress.legislators", {"identity_test": "true"}, mode="manual")
    with run:
        pass
    with connect() as conn:
        artifact = conn.execute(
            "INSERT INTO ingest.artifact (dataset_id, remote_url, local_path, artifact_key, status) "
            "VALUES ('congress.legislators', 'https://example.test', '/none', %s, 'planned') "
            "RETURNING artifact_id",
            (f"{PREFIX}-{uuid.uuid4().hex}",),
        ).fetchone()["artifact_id"]
        conn.commit()
    return artifact, run.run_id


def _legislators(bioguide: str, *others: tuple[str, str], name: str = "Legis Person"):
    artifact, run_id = _run_and_artifact()
    rows = [(bioguide, name, None, None, ns, ext, artifact, run_id)
            for ns, ext in (("bioguide", bioguide), *others)]
    with connect() as conn:
        result = promote_legislators(conn, rows)
        conn.commit()
    return result


_FAKE_OPENSTATES: list[bool] = []  # set only when this module created the stand-in


def _fake_openstates(*people: tuple[str, str, list[tuple[str, str]]]) -> None:
    """A stand-in for the FDW schema; refuses to touch a real one."""
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'openstates_source'"
        ).fetchone()
        tables = conn.execute(
            "SELECT count(*) AS n FROM information_schema.tables WHERE table_schema = 'openstates_source'"
        ).fetchone()["n"]
        if exists and tables:
            pytest.skip("openstates_source is a real schema here; not replacing it")
        conn.execute("CREATE SCHEMA IF NOT EXISTS openstates_source")
        _FAKE_OPENSTATES[:] = [True]
        conn.execute(
            "CREATE TABLE openstates_source.opencivicdata_person (id text PRIMARY KEY, name text, "
            "given_name text, family_name text, extras jsonb, current_jurisdiction_id text)"
        )
        conn.execute(
            "CREATE TABLE openstates_source.opencivicdata_personidentifier "
            "(person_id text, scheme text, identifier text)"
        )
        for ocd, name, ids in people:
            conn.execute(
                "INSERT INTO openstates_source.opencivicdata_person VALUES (%s, %s, NULL, NULL, '{}', "
                "'ocd-jurisdiction/country:us/government')",
                (ocd, name),
            )
            for scheme, identifier in ids:
                conn.execute(
                    "INSERT INTO openstates_source.opencivicdata_personidentifier VALUES (%s, %s, %s)",
                    (ocd, scheme, identifier),
                )
        conn.commit()


def _openstates_sync() -> dict:
    with connect() as conn:
        result = sync_openstates_federal_people(conn)
        conn.commit()
    return result


def _drop_fake_openstates() -> None:
    """Drop only the tables this module made; never a real FDW schema."""
    if not _FAKE_OPENSTATES:
        return
    with connect() as conn:
        conn.execute("DROP TABLE IF EXISTS openstates_source.opencivicdata_personidentifier")
        conn.execute("DROP TABLE IF EXISTS openstates_source.opencivicdata_person")
        conn.commit()


def _world(order: str) -> set[frozenset[tuple[str, str]]]:
    """Load one member three ways in the given order; return persons as identifier sets."""
    marker = uuid.uuid4().hex[:6]
    bg, ocd, fec, only_ocd, only_bg = (f"{PREFIX}-{marker}-{x}" for x in ("bg", "ocd", "fec", "ocd2", "bg2"))
    _drop_fake_openstates()
    _fake_openstates(
        (ocd, "Common Name", [("bioguide", bg), ("fec", fec)]),
        (only_ocd, "State Only", [("bioguide", only_bg)]),
    )
    steps = {
        "legislators": lambda: (_legislators(bg, ("fec", fec)), _legislators(only_bg)),
        "openstates": _openstates_sync,
    }
    for step in order.split(","):
        steps[step]()
    with connect() as conn:
        rows = conn.execute(
            "SELECT person_id, namespace, external_id FROM core.person_identifier WHERE external_id LIKE %s",
            (f"{PREFIX}-{marker}-%",),
        ).fetchall()
    people: dict = {}
    for r in rows:
        people.setdefault(r["person_id"], set()).add((r["namespace"], r["external_id"].replace(marker, "X")))
    _drop_fake_openstates()
    return {frozenset(v) for v in people.values()}


def test_load_order_does_not_change_people_or_identifiers(catalog_database: None) -> None:
    """CAP-1: legislators first and OpenStates first give identical person and identifier sets."""
    forward = _world("legislators,openstates")
    backward = _world("openstates,legislators")
    assert forward == backward
    assert len(forward) == 2  # one person per member, none split by the order
    member = next(p for p in forward if ("ocd", f"{PREFIX}-X-ocd") in p)
    assert {ns for ns, _ in member} >= {"bioguide", "ocd", "fec"}


def test_openstates_after_legislators_attaches_to_the_bioguide_person(catalog_database: None) -> None:
    bg, ocd = _ids(2)
    _legislators(bg)
    person = _owner("bioguide", bg)
    _fake_openstates((ocd, "Common", [("bioguide", bg)]))
    try:
        counts = _openstates_sync()
    finally:
        _drop_fake_openstates()
    assert _owner("ocd", ocd) == person
    assert counts["people_created"] == 0 and counts["identifier_conflicts"] == 0


def _two_owners():
    """Two persons and one asserted set that reaches both (never through two BioGuide ids)."""
    bg, ocd, fec, govtrack = _ids(4)
    first = _resolve([("govtrack", govtrack)])["person_id"]
    second = _resolve([("fec", fec)])["person_id"]
    return first, second, [("ocd", ocd), ("bioguide", bg), ("govtrack", govtrack), ("fec", fec)]


def test_two_owners_write_nothing_and_record_one_conflict(catalog_database: None) -> None:
    """CAP-2: a record whose identifiers belong to two persons is never guessed at."""
    first, second, asserted = _two_owners()
    ocd, bg = asserted[0], asserted[1]
    for _ in range(2):  # a rerun must not add a second record
        result = _resolve(asserted)
        assert result["outcome"] == "multiple_owners" and result["person_id"] is None
    assert _owner(*ocd) is None and _owner(*bg) is None  # nothing was written for the record
    assert len(_identifiers_of(first)) == 1 and len(_identifiers_of(second)) == 1
    rows = [r for r in _conflicts("multiple_owners") if r["subject"] == f"test:{ocd[1]}"]
    assert [tuple(r["person_ids"]) for r in rows] == [tuple(sorted([first, second]))]  # one record


def test_conflict_record_is_idempotent_per_owners_and_counts_reruns(catalog_database: None) -> None:
    _, _, asserted = _two_owners()
    for _ in range(3):
        _resolve(asserted)
    [row] = [r for r in _conflicts("multiple_owners") if r["subject"] == f"test:{asserted[0][1]}"]
    assert row["seen_count"] == 3


def test_a_second_bioguide_on_one_person_is_a_conflict(catalog_database: None) -> None:
    b1, b2, ocd = _ids(3)
    person = _resolve([("bioguide", b1), ("ocd", ocd)])["person_id"]
    result = _resolve([("ocd", ocd), ("bioguide", b2)])
    assert result["outcome"] == "bioguide_mismatch"
    assert _owner("bioguide", b2) is None
    assert _identifiers_of(person) == {("bioguide", b1), ("ocd", ocd)}
    assert [r["subject"] for r in _conflicts("bioguide_mismatch") if ocd in r["subject"]] == [f"test:{ocd}"]


def test_identifier_owned_by_another_person_never_moves(catalog_database: None) -> None:
    bg, fec = _ids(2)
    owner = _resolve([("fec", fec)])["person_id"]
    result = _resolve([("bioguide", bg), ("fec", fec)])
    assert result["outcome"] == "matched" and result["person_id"] == owner
    assert _owner("fec", fec) == owner and _owner("bioguide", bg) == owner  # attached, none moved


def test_congress_gov_member_matches_an_existing_person(catalog_database: None) -> None:
    (bg,) = _ids()
    person = _resolve([("bioguide", bg)])["person_id"]
    member = {"bioguideId": bg, "directOrderName": "Someone", "firstName": "S", "lastName": "One"}
    assert upsert_congress_person(member) == str(person)
    assert upsert_congress_person(member) == str(person)  # idempotent


def test_reviewed_duplicate_is_never_created_from_scratch(catalog_database: None) -> None:
    """A rebuild sees the OCD placeholder after the survivor exists: it attaches, not duplicates."""
    survivor_bg, dup_ocd = _ids(2)
    exception = SamePerson("zztest-identity-x", ("bioguide", survivor_bg), ("ocd", dup_ocd))
    person = _resolve([("bioguide", survivor_bg)])["person_id"]
    result = _resolve([("ocd", dup_ocd)], exceptions=[exception])
    assert result["outcome"] == "matched" and result["person_id"] == person
    assert _owner("ocd", dup_ocd) == person
    assert linked_identifiers([("ocd", dup_ocd)], [exception]) == [("ocd", dup_ocd), ("bioguide", survivor_bg)]


def test_exception_file_has_the_stutzman_decision_by_identifier() -> None:
    [stutzman] = [e for e in load_same_person() if e.id == "stutzman-openstates-placeholder"]
    assert stutzman.survivor == ("bioguide", "S001188")
    assert stutzman.duplicate[0] == "ocd"  # identifiers only; the file names no name to match


def _seed_merge_case():
    """A survivor and a placeholder duplicate that already exist, as live has them."""
    survivor_bg, dup_ocd = _ids(2)
    survivor = _resolve([("bioguide", survivor_bg)])["person_id"]
    duplicate = _resolve([("ocd", dup_ocd)])["person_id"]
    exception = SamePerson(f"{PREFIX}-{uuid.uuid4().hex[:6]}", ("bioguide", survivor_bg), ("ocd", dup_ocd))
    return survivor, duplicate, exception


def _merge(exception: SamePerson):
    with connect() as conn:
        result = merge_person(conn, exception)
        conn.commit()
    return result


def _seat(person, bioguide: str, artifact, run_id, stated_name: str = "Roster Name"):
    """One current committee seat, linked the way the loader links it: person owns that BioGuide."""
    thomas_key = _ids()[0]
    with connect() as conn:
        committee = conn.execute(
            "INSERT INTO core.committee (thomas_key, kind, chamber, name, source_artifact_id, run_id) "
            "VALUES (%s, 'committee', 'house', 'Identity test committee', %s, %s) "
            "RETURNING committee_id",
            (thomas_key, artifact, run_id),
        ).fetchone()["committee_id"]
        assignment = conn.execute(
            "INSERT INTO core.committee_assignment "
            "(committee_id, person_id, bioguide, party, rank, stated_name, chamber, "
            "source_artifact_id, run_id) "
            "VALUES (%s, %s, %s, 'majority', 1, %s, 'house', %s, %s) "
            "RETURNING committee_assignment_id",
            (committee, person, bioguide, stated_name, artifact, run_id),
        ).fetchone()["committee_assignment_id"]
        conn.commit()
    return committee, assignment


def test_merge_moves_a_committee_seat_with_its_bioguide(catalog_database: None) -> None:
    """The allowed merge: the survivor has no BioGuide, the duplicate's seat follows them."""
    survivor_ocd, roster_id = _ids(2)
    survivor = _resolve([("ocd", survivor_ocd)])["person_id"]
    duplicate = _resolve([("bioguide", roster_id)])["person_id"]
    exception = SamePerson(f"{PREFIX}-{uuid.uuid4().hex[:6]}", ("ocd", survivor_ocd), ("bioguide", roster_id))
    artifact, run_id = _run_and_artifact()
    committee, assignment = _seat(duplicate, roster_id, artifact, run_id)
    result = _merge(exception)
    assert result["status"] == "merged"
    assert result["counts"]["core.committee_assignment"] == 1
    assert result["counts"]["core.person_identifier"] == 1
    with connect() as conn:
        row = conn.execute(
            "SELECT committee_assignment_id, committee_id, person_id, bioguide, party, rank, stated_name "
            "FROM core.committee_assignment WHERE committee_assignment_id = %s",
            (assignment,),
        ).fetchone()
        audit = conn.execute(
            "SELECT counts FROM ingest.person_merge WHERE exception_id = %s",
            (exception.id,),
        ).fetchone()
        assert conn.execute("SELECT 1 FROM core.person WHERE person_id = %s", (duplicate,)).fetchone() is None
    assert row["person_id"] == survivor
    assert row["bioguide"] == roster_id and row["stated_name"] == "Roster Name"
    assert row["party"] == "majority" and row["rank"] == 1 and row["committee_id"] == committee
    assert audit["counts"]["core.committee_assignment"] == 1
    assert _owner("bioguide", roster_id) == survivor
    assert _merge(exception)["status"] == "already_merged"


def test_merge_of_two_bioguides_leaves_committee_seats(catalog_database: None) -> None:
    """Two BioGuide ids are two people. Their seats stay where they were."""
    first_bg, second_bg = _ids(2)
    first = _resolve([("bioguide", first_bg)])["person_id"]
    second = _resolve([("bioguide", second_bg)])["person_id"]
    artifact, run_id = _run_and_artifact()
    _, first_seat = _seat(first, first_bg, artifact, run_id, stated_name="First")
    _, second_seat = _seat(second, second_bg, artifact, run_id, stated_name="Second")
    with pytest.raises(ValueError, match="two people"):
        _merge(SamePerson(f"{PREFIX}-two-bioguides-seats", ("bioguide", first_bg), ("bioguide", second_bg)))
    with connect() as conn:
        rows = conn.execute(
            "SELECT committee_assignment_id, person_id FROM core.committee_assignment "
            "WHERE committee_assignment_id IN (%s, %s)",
            (first_seat, second_seat),
        ).fetchall()
    assert {row["committee_assignment_id"]: row["person_id"] for row in rows} == {
        first_seat: first,
        second_seat: second,
    }


def test_merge_moves_identifiers_and_deletes_the_duplicate(catalog_database: None) -> None:
    """CAP-3: identifier attached to the survivor, duplicate gone, audit row written, rerun a no-op."""
    survivor, duplicate, exception = _seed_merge_case()
    result = _merge(exception)
    assert result["status"] == "merged" and result["counts"]["core.person_identifier"] == 1
    assert _owner("ocd", exception.duplicate[1]) == survivor
    with connect() as conn:
        assert conn.execute("SELECT 1 FROM core.person WHERE person_id = %s", (duplicate,)).fetchone() is None
        audit = conn.execute(
            "SELECT survivor_person_id, duplicate_person_id, counts FROM ingest.person_merge "
            "WHERE exception_id = %s", (exception.id,)
        ).fetchone()
    assert (audit["survivor_person_id"], audit["duplicate_person_id"]) == (survivor, duplicate)
    assert _merge(exception)["status"] == "already_merged"


def test_merge_when_the_duplicate_was_never_created_is_a_no_op(catalog_database: None) -> None:
    bg, ocd = _ids(2)
    _resolve([("bioguide", bg)])
    assert _merge(SamePerson(f"{PREFIX}-none", ("bioguide", bg), ("ocd", ocd)))["status"] == "already_merged"


def _roll_calls(conn, count: int) -> list[uuid.UUID]:
    return [
        conn.execute(
            "INSERT INTO core.roll_call (jurisdiction, legislative_session, external_id) "
            "VALUES (%s, 'test', %s) RETURNING roll_call_id",
            (f"{PREFIX}-jurisdiction", f"{PREFIX}-{uuid.uuid4().hex}"),
        ).fetchone()["roll_call_id"]
        for _ in range(count)
    ]


def test_merge_preserves_colliding_votes_and_moves_the_rest(catalog_database: None) -> None:
    survivor, duplicate, exception = _seed_merge_case()
    artifact, _ = _run_and_artifact()
    with connect() as conn:
        rolls = _roll_calls(conn, 2)
        for roll, person, position in (
            (rolls[0], survivor, "yea"), (rolls[0], duplicate, "nay"), (rolls[1], duplicate, "yea"),
        ):
            conn.execute(
                "INSERT INTO fact.member_vote (roll_call_id, person_id, position, source_artifact_id) "
                "VALUES (%s, %s, %s, %s)", (roll, person, position, artifact),
            )
        conn.commit()
    result = _merge(exception)
    assert result["counts"]["member_vote_preserved"] == 1
    assert result["counts"]["fact.member_vote"] == 1
    with connect() as conn:
        held = conn.execute(
            "SELECT roll_call_id, person_id, position FROM fact.member_vote WHERE roll_call_id = ANY(%s)", (rolls,)
        ).fetchall()
        kept = conn.execute(
            "SELECT v.vote FROM ingest.person_merge_vote v JOIN ingest.person_merge m USING (person_merge_id) "
            "WHERE m.exception_id = %s AND v.roll_call_id = %s", (exception.id, rolls[0])
        ).fetchall()
    assert {(r["roll_call_id"], r["person_id"], r["position"]) for r in held} == {
        (rolls[0], survivor, "yea"),  # the survivor's own vote stands
        (rolls[1], survivor, "yea"),  # the duplicate's other vote moved
    }
    [audit] = kept
    assert audit["vote"]["position"] == "nay" and audit["vote"]["person_id"] == str(duplicate)


def test_merge_aborts_on_colliding_terms_and_changes_nothing(catalog_database: None) -> None:
    survivor, duplicate, exception = _seed_merge_case()
    artifact, _ = _run_and_artifact()
    with connect() as conn:
        org = conn.execute(
            "INSERT INTO core.organization (name, organization_type, jurisdiction_geoid, metadata) "
            "VALUES ('identity test', 'lower', 'zz', '{\"identity_test\": true}') RETURNING organization_id"
        ).fetchone()["organization_id"]
        for person in (survivor, duplicate):
            conn.execute(
                "INSERT INTO core.membership (person_id, organization_id, role, start_date, source_artifact_id) "
                "VALUES (%s, %s, 'member', '2001-01-03', %s)", (person, org, artifact),
            )
        conn.commit()
    try:
        with pytest.raises(ValueError, match="collide"):
            _merge(exception)
        assert _owner("ocd", exception.duplicate[1]) == duplicate  # nothing moved
    finally:
        with connect() as conn:
            conn.execute("DELETE FROM core.membership WHERE organization_id = %s", (org,))
            conn.execute("DELETE FROM core.organization WHERE organization_id = %s", (org,))
            conn.commit()


def test_merge_covers_every_table_that_references_a_person(catalog_database: None) -> None:
    """A table added later cannot be forgotten by the merge."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT conrelid::regclass::text AS t FROM pg_constraint "
            "WHERE contype = 'f' AND confrelid = 'core.person'::regclass"
        ).fetchall()
    referencing = {r["t"] for r in rows} - {
        "ingest.person_merge"  # the audit row of the survivor itself, never repointed
    }
    assert referencing == set(PERSON_REFERENCES)


def test_person_creators_share_one_lock(catalog_database: None) -> None:
    """A second writer waits for the first to commit instead of creating a duplicate."""
    (bg,) = _ids()
    with connect() as holder, connect() as waiter:
        cur = holder.cursor()
        first = resolve_person(cur, [("bioguide", bg)], dataset_id="congress.legislators",
                               subject=f"test:{bg}", new_person=_new("First"), exceptions=[])
        waiter.execute("SET lock_timeout = '300ms'")
        with pytest.raises(Exception, match="lock timeout|canceling statement"):
            resolve_person(waiter.cursor(), [("bioguide", bg)], dataset_id="congress.legislators",
                           subject=f"test:{bg}", new_person=_new("Second"), exceptions=[])
        waiter.rollback()
        holder.commit()
    again = _resolve([("bioguide", bg)])
    assert again["outcome"] == "matched" and again["person_id"] == first["person_id"]


def _cli_case(tmp_path, monkeypatch):
    """Two fresh people and a temporary exceptions file naming them; never the real ids."""
    from opendiscourse_research import identity_merge

    survivor_bg, dup_ocd = _ids(2)
    survivor = _resolve([("bioguide", survivor_bg)])["person_id"]
    duplicate = _resolve([("ocd", dup_ocd)])["person_id"]
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(
        "exceptions:\n"
        f"  - id: {PREFIX}-cli-{uuid.uuid4().hex[:6]}\n    decision: same_person\n"
        f"    survivor: {{namespace: bioguide, external_id: {survivor_bg}}}\n"
        f"    duplicate: {{namespace: ocd, external_id: {dup_ocd}}}\n"
    )
    monkeypatch.setattr(identity_merge, "EXCEPTIONS_PATH", exceptions)
    return survivor, duplicate, dup_ocd


def _invoke(*args: str):
    import json

    from typer.testing import CliRunner

    from opendiscourse_research.cli import app

    result = CliRunner().invoke(app, ["merge-people", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_merge_people_dry_run_reports_and_keeps_nothing(catalog_database: None, tmp_path, monkeypatch) -> None:
    _, duplicate, dup_ocd = _cli_case(tmp_path, monkeypatch)
    [merge] = _invoke("--dry-run")["merges"]
    assert merge["status"] == "merged" and merge["counts"]["core.person_identifier"] == 1
    assert _owner("ocd", dup_ocd) == duplicate  # rolled back


def test_merge_people_applies_and_persists(catalog_database: None, tmp_path, monkeypatch) -> None:
    survivor, _, dup_ocd = _cli_case(tmp_path, monkeypatch)
    assert _invoke()["merges"][0]["status"] == "merged"
    assert _owner("ocd", dup_ocd) == survivor
    assert _invoke()["merges"][0]["status"] == "already_merged"


def test_merge_with_missing_survivor_is_reported_not_raised(catalog_database: None) -> None:
    (ocd,) = _ids()
    _resolve([("ocd", ocd)])
    exception = SamePerson(f"{PREFIX}-nosurvivor", ("bioguide", f"{PREFIX}-absent"), ("ocd", ocd))
    assert _merge(exception)["status"] == "survivor_missing"


def test_merge_refuses_two_different_bioguide_ids(catalog_database: None) -> None:
    b1, b2 = _ids(2)
    _resolve([("bioguide", b1)])
    _resolve([("bioguide", b2)])
    with pytest.raises(ValueError, match="two people"):
        _merge(SamePerson(f"{PREFIX}-two-bioguides", ("bioguide", b1), ("bioguide", b2)))
    assert _owner("bioguide", b2) is not None and _owner("bioguide", b1) != _owner("bioguide", b2)


def test_a_merge_survivor_can_itself_be_merged_later(catalog_database: None) -> None:
    """Chain A -> B -> C: the audit row of the first merge follows its survivor."""
    c_bg, b_ocd, a_ocd = _ids(3)
    c = _resolve([("bioguide", c_bg)])["person_id"]
    b = _resolve([("ocd", b_ocd)])["person_id"]
    _resolve([("ocd", a_ocd)])
    first = SamePerson(f"{PREFIX}-chain-1", ("ocd", b_ocd), ("ocd", a_ocd))
    second = SamePerson(f"{PREFIX}-chain-2", ("bioguide", c_bg), ("ocd", b_ocd))
    assert _merge(first)["status"] == "merged"
    assert _merge(second)["status"] == "merged"
    assert _owner("ocd", a_ocd) == c and _owner("ocd", b_ocd) == c
    with connect() as conn:
        rows = conn.execute(
            "SELECT survivor_person_id FROM ingest.person_merge WHERE exception_id = %s", (first.id,)
        ).fetchall()
    assert [r["survivor_person_id"] for r in rows] == [c] and b != c


def test_chained_exceptions_link_every_hop() -> None:
    chain = [
        SamePerson("x1", ("ocd", "b"), ("ocd", "a")),
        SamePerson("x2", ("bioguide", "c"), ("ocd", "b")),
    ]
    assert linked_identifiers([("ocd", "a")], chain) == [("ocd", "a"), ("ocd", "b"), ("bioguide", "c")]


def test_merge_resolves_conflicts_that_named_the_duplicate(catalog_database: None) -> None:
    bg, ocd = _ids(2)
    survivor = _resolve([("bioguide", bg)])["person_id"]
    duplicate = _resolve([("ocd", ocd)])["person_id"]
    _resolve([("ocd", ocd), ("bioguide", bg)])  # two owners: recorded as a conflict
    [conflict] = [r for r in _conflicts("multiple_owners") if r["subject"] == f"test:{ocd}"]
    assert conflict["resolved_at"] is None
    _merge(SamePerson(f"{PREFIX}-conflict", ("bioguide", bg), ("ocd", ocd)))
    [conflict] = [r for r in _conflicts("multiple_owners") if r["subject"] == f"test:{ocd}"]
    assert conflict["resolved_at"] is not None and "merged" in conflict["resolution"]
    _resolve([("ocd", ocd), ("bioguide", bg)])  # now one owner: matched, no new conflict
    assert len([r for r in _conflicts("multiple_owners") if r["subject"] == f"test:{ocd}"]) == 1
    assert survivor and duplicate


def test_a_recurring_conflict_reopens(catalog_database: None) -> None:
    _, _, asserted = _two_owners()
    subject = f"test:{asserted[0][1]}"
    _resolve(asserted)
    with connect() as conn:
        conn.execute(
            "UPDATE ingest.identity_conflict SET resolved_at = now(), resolution = 'x' WHERE subject = %s",
            (subject,),
        )
        conn.commit()
    _resolve(asserted)
    [row] = [r for r in _conflicts("multiple_owners") if r["subject"] == subject]
    assert row["resolved_at"] is None and row["seen_count"] == 2


def test_two_bioguide_ids_in_one_assertion_is_a_conflict_even_for_a_new_person(catalog_database: None) -> None:
    b1, b2 = _ids(2)
    result = _resolve([("bioguide", b1), ("bioguide", b2)])
    assert result["outcome"] == "bioguide_mismatch"
    assert _owner("bioguide", b1) is None and _owner("bioguide", b2) is None


def test_no_identifier_is_refused_not_created(catalog_database: None) -> None:
    with pytest.raises(ValueError, match="at least one identifier"):
        _resolve_empty()


def _resolve_empty():
    with connect() as conn:
        resolve_person(conn.cursor(), [], dataset_id="congress.legislators", subject="test:none",
                       new_person=_new("T"), exceptions=[])


def test_legislators_load_flags_a_second_bioguide_on_one_person(catalog_database: None) -> None:
    b1, b2, fec = _ids(3)
    person = _resolve([("bioguide", b1), ("fec", fec)])["person_id"]
    result = _legislators(b2, ("fec", fec))
    [conflict] = result["conflicts"]
    assert conflict["kind"] == "bioguide_mismatch" and conflict["person_ids"] == [str(person)]
    assert _owner("bioguide", b2) is None and _identifiers_of(person) == {("bioguide", b1), ("fec", fec)}
    assert result["identifiers_already_present"] == 0 and result["identifiers_created"] == 0


def test_legislators_in_one_file_cannot_share_an_owner(catalog_database: None) -> None:
    """Two BioGuide ids reaching one person through different identifiers is a conflict for both."""
    b1, b2, fec, govtrack = _ids(4)
    person = _resolve([("fec", fec), ("govtrack", govtrack)])["person_id"]
    artifact, run_id = _run_and_artifact()
    rows = [
        (b1, "Legis Person", None, None, ns, ext, artifact, run_id)
        for ns, ext in (("bioguide", b1), ("fec", fec))
    ] + [
        (b2, "Legis Person", None, None, ns, ext, artifact, run_id)
        for ns, ext in (("bioguide", b2), ("govtrack", govtrack))
    ]
    with connect() as conn:
        result = promote_legislators(conn, rows)
        conn.commit()
    assert {c["kind"] for c in result["conflicts"]} == {"bioguide_mismatch"} and len(result["conflicts"]) == 2
    assert _owner("bioguide", b1) is None and _owner("bioguide", b2) is None
    assert _identifiers_of(person) == {("fec", fec), ("govtrack", govtrack)}


def test_promote_legislators_waits_on_the_shared_identity_lock(catalog_database: None) -> None:
    (bg,) = _ids()
    artifact, run_id = _run_and_artifact()
    rows = [(bg, "Legis Person", None, None, "bioguide", bg, artifact, run_id)]
    with connect() as holder, connect() as waiter:
        resolve_person(holder.cursor(), [("bioguide", f"{bg}-held")], dataset_id="congress.legislators",
                       subject="test:held", new_person=_new("Held"), exceptions=[])
        waiter.execute("SET lock_timeout = '300ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            promote_legislators(waiter, rows)
        holder.rollback()


def test_openstates_sync_reports_conflicts_and_writes_nothing_for_them(catalog_database: None) -> None:
    a, b, ocd = _ids(3)
    _resolve([("bioguide", a)])
    _resolve([("bioguide", b)])
    _fake_openstates((ocd, "Common", [("bioguide", a), ("fec", b)]), (f"{ocd}-2", "Common", []))
    _resolve([("fec", b)])  # a third person owns the fec id, so the record's ids span two owners
    try:
        counts = _openstates_sync()
    finally:
        _drop_fake_openstates()
    assert counts["identifier_conflicts"] == 1 and counts["people"] == 1 and counts["people_created"] == 1
    assert _owner("ocd", ocd) is None
    assert [r["subject"] for r in _conflicts("multiple_owners") if ocd in r["subject"]] == [f"ocd:{ocd}"]


def test_duplicate_first_then_legislators_makes_one_person(catalog_database: None) -> None:
    """The order that used to create the duplicate: the OCD placeholder before the BioGuide load."""
    bg, ocd = _ids(2)
    exception = SamePerson(f"{PREFIX}-dup-first", ("bioguide", bg), ("ocd", ocd))
    first = _resolve([("ocd", ocd)], exceptions=[exception])
    assert _identifiers_of(first["person_id"]) == {("ocd", ocd), ("bioguide", bg)}
    result = _legislators(bg)
    assert result["people_created"] == 0 and result["conflicts"] == []
    assert _owner("bioguide", bg) == first["person_id"]
