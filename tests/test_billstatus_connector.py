"""Story 9.5 database contract: the BILLSTATUS Connector, download -> inventory -> ingest.

A fake origin serves small synthetic zips for Congress 998, a Congress that does not
exist, so nothing here can touch real rows. Every test starts and ends with those rows
removed: CI runs every DB module against one shared database.
"""

from __future__ import annotations

import hashlib
import io
import os
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from idempotency_harness import IdempotencyCase, check_all

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, connect
from opendiscourse_research.ingestion import billstatus
from opendiscourse_research.ingestion.billstatus import BillStatusConnector
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion.connector import Connector, run_connector
from opendiscourse_research.providers.govinfo import ZIP_URL, GovInfoNotFound, RemoteZip

CONGRESS = 998
KEY = f"BILLSTATUS-{CONGRESS}-hr.zip"
MODIFIED = "Sat, 20 Jan 2024 00:55:38 GMT"
LATER = "Sun, 21 Jan 2024 03:00:00 GMT"


# -- database ---------------------------------------------------------------
@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    """Use CI's PostGIS service or a disposable local one, as the other DB contracts do."""
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
        _remove_rows()
        settings.database_url = original
        _engine.cache_clear()
        if container is not None:
            container.stop()


_BILL_IDS = "(SELECT bill_id FROM core.bill WHERE jurisdiction = 'us' AND legislative_session = '998')"


def _remove_rows() -> None:
    """Delete everything Congress 998 created, children before parents."""
    with connect() as conn:
        for statement in (
            f"DELETE FROM core.bill_document WHERE bill_id IN {_BILL_IDS}",
            f"DELETE FROM core.bill_action WHERE bill_id IN {_BILL_IDS}",
            f"DELETE FROM core.bill_sponsorship WHERE bill_id IN {_BILL_IDS}",
            f"DELETE FROM core.bill_committee WHERE bill_id IN {_BILL_IDS}",
            f"DELETE FROM core.bill_subject WHERE bill_id IN {_BILL_IDS}",
            f"DELETE FROM core.bill_identifier WHERE bill_id IN {_BILL_IDS}",
            "DELETE FROM core.bill WHERE jurisdiction = 'us' AND legislative_session = '998'",
            "DELETE FROM core.document WHERE canonical_url LIKE '%BILLS-998%'",
            "DELETE FROM core.legislative_session WHERE identifier = '998'",
            (
                "DELETE FROM ingest.run_target WHERE run_id IN (SELECT run_id FROM ingest.run "
                "WHERE dataset_id = 'congress.govinfo_billstatus' AND (parameters->'congresses' @> '[998]' "
                "OR parameters->'congresses' @> '[500]'))"
            ),
            (
                "DELETE FROM ingest.run WHERE dataset_id = 'congress.govinfo_billstatus' "
                "AND (parameters->'congresses' @> '[998]' OR parameters->'congresses' @> '[500]')"
            ),
            "DELETE FROM ingest.artifact WHERE artifact_key LIKE 'BILLSTATUS-998-%'",
        ):
            conn.execute(statement)
        conn.commit()


@pytest.fixture(autouse=True)
def _clean(catalog_database: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "lake" / "raw"))
    _remove_rows()
    yield
    _remove_rows()


def _one(sql: str, *params: object):
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
    assert row is not None
    return next(iter(row.values()))


def _rows(sql: str, *params: object) -> list[tuple]:
    with connect() as conn:
        return [tuple(r.values()) for r in conn.execute(sql, params).fetchall()]


# -- synthetic origin ---------------------------------------------------------
def _bill_xml(number: int, *, actions: int = 2, congress: int = CONGRESS, title: str | None = None) -> str:
    items = "".join(
        f"<item><actionDate>2024-01-{a + 1:02d}</actionDate><text>Action {a + 1} on {number}</text>"
        f"<type>Floor</type><actionCode>H{a}</actionCode></item>"
        for a in range(actions)
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<billStatus><version>3.0.0</version><bill>
  <number>{number}</number><type>HR</type><congress>{congress}</congress>
  <introducedDate>2024-01-01</introducedDate>
  <title>{title or f"A bill numbered {number}"}</title>
  <committees><item><systemCode>hsii00</systemCode><name>Natural Resources</name>
    <chamber>House</chamber><type>Standing</type></item></committees>
  <actions>{items}</actions>
  <sponsors><item><bioguideId>T998001</bioguideId><fullName>Rep. Test</fullName>
    <party>D</party><state>XX</state><district>1</district></item></sponsors>
  <cosponsors><item><bioguideId>T998002</bioguideId><fullName>Rep. Two</fullName>
    <sponsorshipDate>2024-01-02</sponsorshipDate><isOriginalCosponsor>N</isOriginalCosponsor></item></cosponsors>
  <policyArea><name>Environmental Protection</name></policyArea>
  <subjects><legislativeSubjects><item><name>Oversight</name></item></legislativeSubjects></subjects>
  <textVersions><item><type>Introduced in House</type><date>2024-01-01T05:00:00Z</date>
    <formats><item><url>https://www.govinfo.gov/content/pkg/BILLS-998hr{number}ih/xml/BILLS-998hr{number}ih.xml</url></item></formats>
  </item></textVersions>
  <latestAction><actionDate>2024-01-02</actionDate><text>Latest on {number}</text></latestAction>
</bill></billStatus>"""


def _zip(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, content in members.items():
            bundle.writestr(name, content)
    return buffer.getvalue()


def _members(numbers: range | list[int], **kwargs) -> dict[str, str]:
    return {f"BILLSTATUS-{CONGRESS}hr{n}.xml": _bill_xml(n, **kwargs) for n in numbers}


class FakeOrigin:
    """Stands in for GovInfo: HEAD, manifest, and the download itself."""

    def __init__(self, tmp: Path, members: dict[str, str]) -> None:
        self.tmp = tmp
        self.downloads: list[str] = []
        self.truncate = False
        self.extra_manifest: set[str] = set()
        self.absent: set[str] = set()
        self.publish(members)

    def publish(self, members: dict[str, str], modified: str = MODIFIED) -> None:
        self.members = members
        self.data = _zip(members)
        self.modified = modified

    # GovInfoBillStatus surface
    def congresses(self) -> list[int]:
        return [CONGRESS]

    def zip_info(self, congress: int, bill_type: str) -> RemoteZip:
        if bill_type in self.absent:
            raise GovInfoNotFound(f"{bill_type}: 404")
        return RemoteZip(
            congress,
            bill_type,
            ZIP_URL.format(congress=congress, bill_type=bill_type),
            len(self.data),
            self.modified,
        )

    def manifest_xml(self, congress: int, bill_type: str) -> frozenset[str]:
        return frozenset(self.members) | self.extra_manifest

    # Downloader surface (what bulk.download does, without HTTP)
    def download(self, spec: ArtifactSpec, *, overwrite: bool = False) -> Path:
        self.downloads.append(spec.artifact_key)
        source = self.tmp / f"{spec.artifact_key}.src"
        source.write_bytes(self.data[:-5] if self.truncate else self.data)
        return register_local(spec, source)


@pytest.fixture
def origin(tmp_path: Path) -> FakeOrigin:
    return FakeOrigin(tmp_path, _members(range(1, 4)))


def _sync(origin: FakeOrigin, **kwargs) -> BillStatusConnector:
    connector = BillStatusConnector(
        [CONGRESS],
        ("hr",),
        govinfo=origin,  # type: ignore[arg-type]
        downloader=origin.download,
        sleep=lambda _s: None,
        **kwargs,
    )
    run_connector(connector)
    return connector


def _run_status(congress: int = CONGRESS) -> tuple[str, str | None]:
    row = _rows(
        "SELECT status, code_version FROM ingest.run WHERE dataset_id = 'congress.govinfo_billstatus' "
        "AND parameters->'congresses' @> %s::jsonb ORDER BY started_at DESC LIMIT 1",
        f"[{congress}]",
    )
    return row[0]


def _artifact() -> dict:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM ingest.artifact WHERE artifact_key = %s ORDER BY artifact_version DESC LIMIT 1",
            (KEY,),
        ).fetchone()


def _bills() -> int:
    return _one("SELECT count(*) AS n FROM core.bill WHERE legislative_session = '998'")


# -- the workflow -------------------------------------------------------------
def test_billstatus_connector_satisfies_the_connector_protocol() -> None:
    assert isinstance(BillStatusConnector(), Connector)


def test_first_sync_downloads_inventories_and_loads_with_evidence(origin: FakeOrigin) -> None:
    connector = _sync(origin)

    assert origin.downloads == [KEY]
    assert connector.result["downloaded"] == 1 and connector.result["bills_loaded"] == 3
    assert connector.result["partial"] is False
    artifact = _artifact()
    assert artifact["status"] == "loaded" and artifact["artifact_version"] == 1
    assert artifact["checksum_sha256"] == hashlib.sha256(origin.data).hexdigest()
    assert artifact["remote_url"] == ZIP_URL.format(congress=CONGRESS, bill_type="hr")
    assert artifact["metadata"]["remote_size"] == len(origin.data)
    assert artifact["metadata"]["remote_last_modified"] == MODIFIED
    assert artifact["metadata"]["coverage"]["status"] == "complete"
    assert Path(artifact["local_path"]).is_file() and str(settings.data_root) in artifact["local_path"]
    # every fact resolves to the run and the artifact
    assert _one(
        "SELECT count(*) AS n FROM core.bill_action a JOIN core.bill b USING (bill_id) "
        "WHERE b.legislative_session = '998' AND a.source_artifact_id = %s",
        artifact["artifact_id"],
    ) == 6
    assert _one("SELECT count(*) AS n FROM core.bill_sponsorship s JOIN core.bill b USING (bill_id) "
                "WHERE b.legislative_session = '998'") == 6
    status, code_version = _run_status()
    assert status == "succeeded" and code_version
    targets = _rows(
        "SELECT t.target, t.coverage_key, t.rows_inserted, t.status FROM ingest.run_target t JOIN ingest.run r USING (run_id) "
        "WHERE r.dataset_id = 'congress.govinfo_billstatus' AND r.parameters->'congresses' @> '[998]' ORDER BY 1"
    )
    assert targets == [
        ("core.bill", "congress=998", 3, "succeeded"),
        ("core.bill_action", "congress=998", 6, "succeeded"),
    ]


def test_unchanged_rerun_makes_no_download_and_no_change(origin: FakeOrigin) -> None:
    _sync(origin)
    connector = _sync(origin)

    assert origin.downloads == [KEY]  # only the first run fetched bytes
    assert connector.result["reused"] == 1 and connector.result["bills_loaded"] == 0
    assert connector.result["items"][0]["already_loaded"] == 3
    assert _one("SELECT count(*) AS n FROM ingest.artifact WHERE artifact_key = %s", KEY) == 1


def test_download_only_registers_bytes_and_a_later_sync_loads_without_refetching(
    origin: FakeOrigin,
) -> None:
    _sync(origin, download_only=True)
    assert _bills() == 0 and _artifact()["status"] == "downloaded"

    _sync(origin)
    assert origin.downloads == [KEY] and _bills() == 3 and _artifact()["status"] == "loaded"


def test_changed_origin_appends_a_version_and_replaces_the_old_rows(origin: FakeOrigin) -> None:
    _sync(origin)
    first = _artifact()
    origin.publish({**_members(range(1, 4)), **_members([1], actions=3), **_members([4])}, LATER)

    connector = _sync(origin)

    assert origin.downloads == [KEY, KEY]
    item = connector.result["items"][0]
    assert item["action"] == "download" and item["reason"] == "changed at the origin"
    second = _artifact()
    assert second["artifact_version"] == 2 and second["artifact_id"] != first["artifact_id"]
    assert _bills() == 4
    # bill 1 now has 3 actions, the others 2: no duplicates from the older version
    assert _one("SELECT count(*) AS n FROM core.bill_action a JOIN core.bill b USING (bill_id) "
                "WHERE b.legislative_session = '998'") == 3 + 2 + 2 + 2
    for table in ("bill_action", "bill_sponsorship", "bill_committee", "bill_subject"):
        assert _one(f"SELECT count(*) AS n FROM core.{table} WHERE source_artifact_id = %s",
                    first["artifact_id"]) == 0
    assert connector.result["superseded_rows_replaced"] > 0
    # the older version's bytes are evidence and stay registered and on disk
    assert _one("SELECT count(*) AS n FROM ingest.artifact WHERE artifact_id = %s", first["artifact_id"]) == 1
    assert Path(first["local_path"]).is_file()


def test_registry_row_with_no_recorded_origin_state_is_verified_by_download(
    origin: FakeOrigin, tmp_path: Path
) -> None:
    """An artifact this Connector did not write is re-verified against the origin, not trusted."""
    legacy = tmp_path / "legacy.zip"
    legacy.write_bytes(origin.data)
    register_local(
        ArtifactSpec("congress.govinfo_billstatus", KEY, "https://old.example/x.zip", f"{CONGRESS}/{KEY}"),
        legacy,
    )

    connector = _sync(origin)

    item = connector.result["items"][0]
    assert item["action"] == "download" and item["reason"] == "not yet verified against the origin"
    artifact = _artifact()
    assert artifact["artifact_version"] == 1  # same bytes: the same version, now origin-stamped
    assert artifact["metadata"]["remote_size"] == len(origin.data)
    assert _bills() == 3


def test_refetched_bytes_of_a_wrong_size_are_never_ingested(origin: FakeOrigin) -> None:
    origin.truncate = True
    with pytest.raises(RuntimeError, match="reports"):
        _sync(origin)
    assert _bills() == 0
    assert _run_status()[0] == "failed"
    # a later run sees the retained file's size disagree with the origin and fetches it again
    origin.truncate = False
    connector = _sync(origin)
    assert connector.result["items"][0]["reason"] == "retained size differs from the origin"
    assert _bills() == 3


def test_manifest_disagreement_loads_but_reports_the_run_partial(origin: FakeOrigin) -> None:
    origin.extra_manifest = {"BILLSTATUS-998hr99.xml"}  # GovInfo lists a bill the zip lacks
    connector = _sync(origin)

    assert connector.result["partial"] is True
    assert connector.result["incomplete_zips"][0]["missing"] == 1
    assert _bills() == 3
    assert _run_status()[0] == "partial"
    assert _artifact()["metadata"]["coverage"]["status"] == "partial"
    partial_target = _rows(
        "SELECT status FROM ingest.run_target WHERE target = 'core.bill' AND coverage_key = 'congress=998'"
    )
    assert partial_target == [("partial",)]


def test_a_malformed_member_is_skipped_reported_and_keeps_the_zip_unfinished(
    origin: FakeOrigin,
) -> None:
    origin.publish({**_members(range(1, 4)), f"BILLSTATUS-{CONGRESS}hr9.xml": "<billStatus><bill>"})
    connector = _sync(origin)

    assert _bills() == 3
    assert connector.result["malformed_members"] == {KEY: [f"BILLSTATUS-{CONGRESS}hr9.xml"]}
    assert connector.result["partial"] is True and _run_status()[0] == "partial"
    assert _artifact()["status"] == "downloaded"  # never claimed as loaded while a member failed


def test_xml_that_contradicts_its_file_name_is_skipped_and_reported(origin: FakeOrigin) -> None:
    """One untrustworthy member must not block 170K others, and must never be written."""
    origin.publish({**_members(range(1, 4)), f"BILLSTATUS-{CONGRESS}hr7.xml": _bill_xml(8)})
    connector = _sync(origin)

    assert _bills() == 3
    assert _one("SELECT count(*) AS n FROM core.bill WHERE bill_number IN ('7', '8') "
                "AND legislative_session = '998'") == 0
    assert connector.result["malformed_members"] == {KEY: [f"BILLSTATUS-{CONGRESS}hr7.xml"]}
    assert "not the bill its name promises" in connector.result["problems"][0]
    assert connector.result["partial"] is True and _run_status()[0] == "partial"
    assert _artifact()["status"] == "downloaded"


def test_a_type_govinfo_does_not_publish_is_reported_not_fatal(origin: FakeOrigin) -> None:
    origin.absent = {"s"}
    connector = BillStatusConnector(
        [CONGRESS],
        ("hr", "s"),
        govinfo=origin,  # type: ignore[arg-type]
        downloader=origin.download,
        sleep=lambda _s: None,
    )
    run_connector(connector)

    assert connector.result["zips"] == 1 and _bills() == 3
    assert connector.result["not_published"] == ["BILLSTATUS-998-s.zip"]
    assert connector.result["partial"] is False and _run_status()[0] == "succeeded"


def test_nothing_published_at_all_is_an_error(origin: FakeOrigin) -> None:
    origin.absent = {"hr"}
    with pytest.raises(RuntimeError, match="publishes none"):
        _sync(origin)
    assert _run_status()[0] == "failed" and origin.downloads == []


def test_a_member_from_another_congress_is_refused_before_any_write(origin: FakeOrigin) -> None:
    origin.publish({**_members(range(1, 4)), "BILLSTATUS-997hr1.xml": _bill_xml(1, congress=997)})
    with pytest.raises(ValueError, match="unexpected member"):
        _sync(origin)
    assert _bills() == 0 and _one("SELECT count(*) AS n FROM core.legislative_session WHERE identifier = '998'") == 0


def test_an_empty_zip_is_refused(origin: FakeOrigin) -> None:
    origin.publish({"readme.txt": "nothing here"})
    with pytest.raises(ValueError, match="no BILLSTATUS XML"):
        _sync(origin)


def test_a_congress_govinfo_does_not_publish_is_an_error() -> None:
    class Nothing:
        def congresses(self) -> list[int]:
            return [108, 109]

    connector = BillStatusConnector([500], ("hr",), govinfo=Nothing())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="not \\[500\\]"):
        run_connector(connector)
    assert _run_status(500)[0] == "failed"


def test_an_interrupt_mid_load_still_closes_the_run_as_failed(origin: FakeOrigin) -> None:
    with _die_on_save(2, error=KeyboardInterrupt), pytest.raises(KeyboardInterrupt):
        _sync(origin)
    assert _run_status()[0] == "failed"
    assert _bills() == 0  # the interrupted batch was rolled back
    _sync(origin)  # and the rerun completes from the registered bytes
    assert _bills() == 3 and origin.downloads == [KEY]


def test_capacity_gate_stops_before_any_download(origin: FakeOrigin) -> None:
    refusal = {
        "approved": False,
        "reason": "insufficient capacity",
        "path": "/x",
        "peak_required_bytes": 10,
        "filesystem_free_bytes": 1,
    }
    with (
        patch.object(billstatus, "storage_preview", return_value=refusal),
        pytest.raises(RuntimeError, match="capacity gate"),
    ):
        _sync(origin)
    assert origin.downloads == [] and _bills() == 0


def test_retained_bytes_are_never_overwritten_by_a_refresh(origin: FakeOrigin) -> None:
    _sync(origin)
    first_path = Path(_artifact()["local_path"])
    before = first_path.read_bytes()
    origin.publish(_members(range(1, 6)), LATER)
    _sync(origin)
    assert first_path.read_bytes() == before


# -- ADR-0003 harness ---------------------------------------------------------
def _digest(rows: list[tuple]) -> str:
    return hashlib.sha256(repr(sorted(rows)).encode()).hexdigest()


def _snapshot() -> dict[str, object]:
    key = "b.bill_type || b.bill_number"
    where = "WHERE b.legislative_session = '998'"
    tables = {
        "bills": "SELECT bill_type, bill_number, title, introduced_date, latest_action_date, latest_action "
        "FROM core.bill b WHERE b.legislative_session = '998'",
        "actions": f"SELECT {key}, a.source_member, a.source_ordinal, a.action_date, a.description "
        f"FROM core.bill_action a JOIN core.bill b USING (bill_id) {where}",
        "sponsorships": f"SELECT {key}, s.member_namespace, s.member_external_id, s.role "
        f"FROM core.bill_sponsorship s JOIN core.bill b USING (bill_id) {where}",
        "committees": f"SELECT {key}, c.external_id, c.name FROM core.bill_committee c "
        f"JOIN core.bill b USING (bill_id) {where}",
        "subjects": f"SELECT {key}, s.external_id, s.label FROM core.bill_subject s "
        f"JOIN core.bill b USING (bill_id) {where}",
        "identifiers": f"SELECT {key}, i.namespace, i.external_id FROM core.bill_identifier i "
        f"JOIN core.bill b USING (bill_id) {where}",
    }
    out: dict[str, object] = {}
    for name, sql in tables.items():
        rows = _rows(sql)
        out[name] = len(rows)
        out[f"{name}_digest"] = _digest(rows)
    return out


@contextmanager
def _die_on_save(call_number: int, error: type[BaseException] = RuntimeError) -> Iterator[None]:
    """Make the Nth bill write raise, like a process killed between two bills."""
    calls = {"n": 0}
    real = billstatus.save_billstatus_bill

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == call_number:
            raise error("killed")
        return real(*args, **kwargs)

    with patch.object(billstatus, "save_billstatus_bill", flaky):
        yield


def test_billstatus_meets_the_load_contract_run_twice_wipe_reload_and_kill_resume(
    tmp_path: Path,
) -> None:
    origin = FakeOrigin(tmp_path, _members(range(1, 6)))

    def wipe() -> None:  # derived rows only; the retained zip and its registry row stay
        with connect() as conn:
            for statement in (
                f"DELETE FROM core.bill_document WHERE bill_id IN {_BILL_IDS}",
                f"DELETE FROM core.bill_action WHERE bill_id IN {_BILL_IDS}",
                f"DELETE FROM core.bill_sponsorship WHERE bill_id IN {_BILL_IDS}",
                f"DELETE FROM core.bill_committee WHERE bill_id IN {_BILL_IDS}",
                f"DELETE FROM core.bill_subject WHERE bill_id IN {_BILL_IDS}",
                f"DELETE FROM core.bill_identifier WHERE bill_id IN {_BILL_IDS}",
                "DELETE FROM core.bill WHERE jurisdiction = 'us' AND legislative_session = '998'",
            ):
                conn.execute(statement)
            conn.commit()

    case = IdempotencyCase(
        name="billstatus",
        load=lambda: _sync(origin, batch_size=2),
        snapshot=_snapshot,
        wipe=wipe,
        interrupt=_die_on_save,
        points=(1, 3, 5),  # first write, mid second batch, the last bill
        atomic=False,  # committed batches stay; the resume must finish the rest
    )
    check_all(case)
    assert _bills() == 5
    assert _one("SELECT count(*) AS n FROM ingest.artifact WHERE artifact_key = %s", KEY) == 1
