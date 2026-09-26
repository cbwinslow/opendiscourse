"""Story 11.3 database contract: the BILLS text Connector, download -> inventory -> ingest.

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
from xml.etree import ElementTree

import pytest
from alembic import command

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import (
    _alembic_config,
    _engine,
    apply_migrations,
    connect,
)
from opendiscourse_research.ingestion import bill_text as bill_text_mod
from opendiscourse_research.ingestion.bill_text import BillTextConnector
from opendiscourse_research.ingestion.bill_text_parse import parse_xml_without_dtd
from opendiscourse_research.ingestion.billstatus_record import record_problems
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion.connector import Connector, run_connector
from opendiscourse_research.providers.govinfo import (
    BILLS_ZIP_URL,
    GovInfoNotFound,
    RemoteZip,
    bills_member_identity,
)
from opendiscourse_research.repositories.artifacts import get_current_artifact

CONGRESS = 998
SESSION = 1
KEY = f"BILLS-{CONGRESS}-{SESSION}-hr.zip"
MODIFIED = "Sat, 20 Jan 2024 00:55:38 GMT"
LATER = "Sun, 21 Jan 2024 03:00:00 GMT"


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
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


def _remove_rows() -> None:
    with connect() as conn:
        for statement in (
            (
                "DELETE FROM core.bill_document WHERE bill_id IN "
                "(SELECT bill_id FROM core.bill WHERE legislative_session = '998')"
            ),
            "DELETE FROM core.bill_text_source_record WHERE congress = 998",
            "DELETE FROM core.bill WHERE jurisdiction = 'us' AND legislative_session = '998'",
            "DELETE FROM core.document WHERE document_type = 'govinfo_bill_text' AND congress = 998",
            (
                "DELETE FROM ingest.run_target WHERE run_id IN (SELECT run_id FROM ingest.run "
                "WHERE dataset_id = 'congress.govinfo_bills')"
            ),
            "DELETE FROM ingest.run WHERE dataset_id = 'congress.govinfo_bills'",
            "DELETE FROM ingest.artifact WHERE dataset_id = 'congress.govinfo_bills'",
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


def _bills_xml(number: int, version: str = "ih", *, title: str | None = None) -> str:
    heading = title or f"A bill numbered {number} ({version})"
    return f"""<?xml version="1.0"?>
<?xml-stylesheet type="text/xsl" href="billres.xsl"?>
<!DOCTYPE bill PUBLIC "-//US Congress//DTDs/bill.dtd//EN" "bill.dtd">
<bill bill-stage="Introduced-in-House" dms-id="H{number}{version}" public-private="public">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dublinCore>
      <dc:title>998 HR {number} {version.upper()}: {heading}</dc:title>
      <dc:publisher>U.S. House of Representatives</dc:publisher>
      <dc:date>2024-01-01</dc:date>
      <dc:format>text/xml</dc:format>
      <dc:language>EN</dc:language>
      <dc:rights>Public domain.</dc:rights>
    </dublinCore>
  </metadata>
  <form>
    <congress>998th CONGRESS</congress>
    <session>1st Session</session>
    <legis-num>H. R. {number}</legis-num>
    <action>
      <action-desc><sponsor name-id="T998001">Rep. Test</sponsor> introduced it</action-desc>
    </action>
    <official-title>{heading}</official-title>
  </form>
  <legis-body id="B{number}">
    <section id="S1"><enum>1.</enum><header>Short title</header>
      <text>The {heading}.</text></section>
  </legis-body>
</bill>"""


def _zip(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, content in members.items():
            bundle.writestr(name, content)
    return buffer.getvalue()


def _members(numbers: range | list[int], versions: tuple[str, ...] = ("ih",)) -> dict[str, str]:
    return {
        f"BILLS-{CONGRESS}hr{n}{version}.xml": _bills_xml(n, version)
        for n in numbers
        for version in versions
    }


class FakeOrigin:
    """Stands in for GovInfo BILLS: HEAD, sessions, manifest, and the download itself."""

    def __init__(self, tmp: Path, members: dict[str, str]) -> None:
        self.tmp = tmp
        self.downloads: list[str] = []
        self.truncate = False
        self.extra_manifest: set[str] = set()
        self.absent: set[str] = set()
        self.listed_congresses = [CONGRESS]
        self.listed_sessions = [SESSION]
        self.publish(members)

    def publish(self, members: dict[str, str], modified: str = MODIFIED) -> None:
        self.members = members
        self.data = _zip(members)
        self.modified = modified

    def congresses(self) -> list[int]:
        return list(self.listed_congresses)

    def sessions(self, congress: int) -> list[int]:
        return list(self.listed_sessions)

    def zip_info(self, congress: int, session: int, bill_type: str) -> RemoteZip:
        if bill_type in self.absent:
            raise GovInfoNotFound(f"{bill_type}: 404")
        return RemoteZip(
            congress,
            bill_type,
            BILLS_ZIP_URL.format(congress=congress, session=session, bill_type=bill_type),
            len(self.data),
            self.modified,
            session,
        )

    def xml_info(self, congress: int, session: int, bill_type: str, name: str) -> RemoteZip:
        if name not in self.members:
            raise GovInfoNotFound(f"{name}: 404")
        body = self.members[name].encode()
        return RemoteZip(
            congress,
            bill_type,
            f"https://www.govinfo.gov/bulkdata/BILLS/{congress}/{session}/{bill_type}/{name}",
            len(body),
            self.modified,
            session,
        )

    def manifest_xml(self, congress: int, session: int, bill_type: str) -> frozenset[str]:
        names = {
            name
            for name in set(self.members) | self.extra_manifest
            if (ident := bills_member_identity(name)) is not None and ident[1] == bill_type
        }
        if bill_type in self.absent and not names:
            raise GovInfoNotFound(f"{bill_type}: 404")
        return frozenset(names)

    def download(self, spec: ArtifactSpec, *, overwrite: bool = False) -> Path:
        self.downloads.append(spec.artifact_key)
        source = self.tmp / f"{spec.artifact_key}.src"
        if spec.artifact_key.endswith(".zip"):
            payload = self.data[:-5] if self.truncate else self.data
        else:
            payload = self.members[Path(spec.artifact_key).name].encode()
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(payload)
        return register_local(spec, source)


@pytest.fixture
def origin(tmp_path: Path) -> FakeOrigin:
    return FakeOrigin(tmp_path, _members(range(1, 4), ("ih", "eh")))


def _sync(origin: FakeOrigin, **kwargs) -> BillTextConnector:
    connector = BillTextConnector(
        [CONGRESS],
        ("hr",),
        (SESSION,),
        govinfo=origin,  # type: ignore[arg-type]
        downloader=origin.download,
        sleep=lambda _s: None,
        **kwargs,
    )
    run_connector(connector)
    return connector


def _seed_bills(*numbers: int) -> None:
    with connect() as conn:
        for number in numbers:
            conn.execute(
                "INSERT INTO core.bill (jurisdiction, legislative_session, bill_type, bill_number, title) "
                "VALUES ('us', '998', 'hr', %s, %s) "
                "ON CONFLICT (jurisdiction, legislative_session, bill_type, bill_number) DO NOTHING",
                (str(number), f"Bill {number}"),
            )
        conn.commit()


def _run_status() -> str:
    return _one(
        "SELECT status FROM ingest.run WHERE dataset_id = 'congress.govinfo_bills' "
        "ORDER BY started_at DESC LIMIT 1"
    )


def _artifact(key: str = KEY) -> dict:
    row = get_current_artifact(key, dataset_id="congress.govinfo_bills")
    assert row is not None
    return row


def _records() -> int:
    return _one("SELECT count(*) AS n FROM core.bill_text_source_record WHERE congress = 998")


@contextmanager
def _die_on_save(call_number: int, error: type[BaseException] = RuntimeError) -> Iterator[None]:
    calls = {"n": 0}
    real = bill_text_mod.save_bill_text

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == call_number:
            raise error("killed")
        return real(*args, **kwargs)

    with patch.object(bill_text_mod, "save_bill_text", flaky):
        yield


def test_bill_text_connector_satisfies_the_connector_protocol() -> None:
    assert isinstance(BillTextConnector([119]), Connector)


def test_first_sync_downloads_inventories_and_loads_records(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    connector = _sync(origin)

    assert origin.downloads == [KEY]
    assert connector.result["downloaded"] == 1
    assert connector.result["versions_loaded"] == 6  # 3 bills × ih, eh
    assert connector.result["partial"] is False
    artifact = _artifact()
    assert artifact["status"] == "loaded" and artifact["artifact_version"] == 1
    assert artifact["checksum_sha256"] == hashlib.sha256(origin.data).hexdigest()
    assert artifact["metadata"]["remote_size"] == len(origin.data)
    assert Path(artifact["local_path"]).is_file()
    assert _records() == 6
    assert _one("SELECT count(*) AS n FROM core.bill_document bd JOIN core.bill b USING (bill_id) "
                "WHERE b.legislative_session = '998'") == 6
    assert _one("SELECT count(*) AS n FROM core.document WHERE document_type = 'govinfo_bill_text' "
                "AND congress = 998 AND version_code IS NOT NULL") == 6
    assert _run_status() == "succeeded"


def test_unknown_bill_is_kept_as_a_record_and_does_not_create_a_bill(origin: FakeOrigin) -> None:
    _seed_bills(1, 2)  # bill 3 is missing
    connector = _sync(origin)

    assert connector.result["partial"] is True
    assert connector.result["unknown_bill_count"] == 2  # ih and eh of bill 3
    assert _one("SELECT count(*) AS n FROM core.bill WHERE legislative_session = '998'") == 2
    assert _records() == 6
    assert _one("SELECT count(*) AS n FROM core.bill_text_source_record "
                "WHERE congress = 998 AND bill_id IS NULL") == 2
    assert _one("SELECT count(*) AS n FROM core.bill_document bd JOIN core.bill b USING (bill_id) "
                "WHERE b.legislative_session = '998'") == 4
    assert _run_status() == "partial"


def test_an_unknown_bill_attaches_on_a_later_sync_without_redownloading(origin: FakeOrigin) -> None:
    _seed_bills(1, 2)
    _sync(origin)
    assert _one("SELECT count(*) AS n FROM core.bill_text_source_record "
                "WHERE congress = 998 AND bill_id IS NULL") == 2
    assert _one("SELECT count(*) AS n FROM core.document WHERE document_type = 'govinfo_bill_text' "
                "AND congress = 998 AND bill_number = '3'") == 0

    _seed_bills(3)
    connector = _sync(origin)

    assert origin.downloads == [KEY]
    assert connector.result["unknown_bill_count"] == 0
    assert _one("SELECT count(*) AS n FROM core.bill_text_source_record "
                "WHERE congress = 998 AND bill_id IS NULL") == 0
    assert _one("SELECT count(*) AS n FROM core.document WHERE document_type = 'govinfo_bill_text' "
                "AND congress = 998 AND bill_number = '3'") == 2
    assert _one(
        "SELECT count(*) AS n FROM core.bill_document bd JOIN core.bill b USING (bill_id) "
        "WHERE b.legislative_session = '998' AND b.bill_number = '3'"
    ) == 2


def test_matching_text_attaches_to_the_existing_bill_id(origin: FakeOrigin) -> None:
    _seed_bills(1)
    _sync(origin)
    bill_id = _one("SELECT bill_id FROM core.bill WHERE bill_number = '1' AND legislative_session = '998'")
    linked = _rows(
        "SELECT d.version_code FROM core.bill_document bd JOIN core.document d USING (document_id) "
        "WHERE bd.bill_id = %s ORDER BY 1",
        bill_id,
    )
    assert [row[0] for row in linked] == ["eh", "ih"]
    assert _one("SELECT count(*) AS n FROM core.bill WHERE bill_number = '1' AND legislative_session = '998'") == 1


def test_unchanged_rerun_makes_no_download_and_no_change(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    _sync(origin)
    connector = _sync(origin)

    assert origin.downloads == [KEY]
    assert connector.result["reused"] == 1 and connector.result["versions_loaded"] == 0
    assert connector.result["items"][0]["already_loaded"] == 6
    assert _one("SELECT count(*) AS n FROM ingest.artifact WHERE artifact_key = %s", KEY) == 1


def test_changed_origin_appends_a_version_and_replaces_the_old_records(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3, 4)
    _sync(origin)
    first = _artifact()
    origin.publish({**_members(range(1, 4), ("ih", "eh")), **_members([4], ("ih",))}, LATER)

    connector = _sync(origin)

    assert origin.downloads == [KEY, KEY]
    second = _artifact()
    assert second["artifact_version"] == 2 and second["artifact_id"] != first["artifact_id"]
    assert _records() == 7
    assert _one(
        "SELECT count(*) AS n FROM core.bill_text_source_record WHERE source_artifact_id = %s",
        first["artifact_id"],
    ) == 0
    assert connector.result["versions_loaded"] == 7
    assert Path(first["local_path"]).is_file()


def test_a_complete_refresh_drops_versions_the_new_zip_no_longer_has(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    _sync(origin)
    assert _records() == 6
    origin.publish(_members(range(1, 3), ("ih", "eh")), LATER)

    _sync(origin)

    assert _records() == 4
    names = {
        row[0]
        for row in _rows("SELECT source_member FROM core.bill_text_source_record")
    }
    assert f"BILLS-{CONGRESS}hr3ih.xml" not in names
    assert f"BILLS-{CONGRESS}hr3eh.xml" not in names


def test_a_downloaded_zip_missing_manifest_xml_is_incomplete_not_unpublished(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    origin.extra_manifest = {f"BILLS-{CONGRESS}hr99ih.xml"}
    connector = _sync(origin)

    assert f"BILLS-{CONGRESS}hr99ih.xml" not in connector.result["not_published"]
    assert connector.result["partial"] is True
    assert connector.result["incomplete_zips"][0]["missing"] == 1
    assert _records() == 6
    assert _run_status() == "partial"
    assert _artifact()["metadata"]["coverage"]["status"] == "partial"


def test_a_type_govinfo_does_not_publish_is_reported_not_fatal(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    origin.absent = {"s"}
    connector = BillTextConnector(
        [CONGRESS],
        ("hr", "s"),
        (SESSION,),
        govinfo=origin,  # type: ignore[arg-type]
        downloader=origin.download,
        sleep=lambda _s: None,
    )
    run_connector(connector)

    assert connector.result["zips"] == 1
    assert KEY.replace("hr", "s") in connector.result["not_published"] or any(
        "s.zip" in n for n in connector.result["not_published"]
    )
    assert connector.result["partial"] is False


def test_fallback_xml_when_the_zip_is_missing(tmp_path: Path) -> None:
    members = _members([1], ("ih",))
    origin = FakeOrigin(tmp_path, members)
    origin.absent = {"hr"}
    _seed_bills(1)
    connector = _sync(origin)

    assert connector.result["xml_fallbacks"] == 1
    assert connector.result["zips"] == 0
    assert _records() == 1
    assert origin.downloads == [f"BILLS-{CONGRESS}-{SESSION}-hr/BILLS-{CONGRESS}hr1ih.xml"]


def test_a_later_zip_replaces_fallback_xml_records(tmp_path: Path) -> None:
    members = _members([1], ("ih",))
    origin = FakeOrigin(tmp_path, members)
    origin.absent = {"hr"}
    _seed_bills(1)
    _sync(origin)
    xml_key = f"BILLS-{CONGRESS}-{SESSION}-hr/BILLS-{CONGRESS}hr1ih.xml"
    xml_artifact = _artifact(xml_key)
    assert _records() == 1
    assert _one(
        "SELECT count(*) AS n FROM core.bill_text_source_record WHERE source_artifact_id = %s",
        xml_artifact["artifact_id"],
    ) == 1

    origin.absent = set()
    connector = _sync(origin)

    assert origin.downloads == [xml_key, KEY]
    assert _records() == 1
    assert _one(
        "SELECT count(*) AS n FROM core.bill_text_source_record WHERE source_artifact_id = %s",
        xml_artifact["artifact_id"],
    ) == 0
    assert _one(
        "SELECT count(*) AS n FROM core.bill_text_source_record WHERE source_artifact_id = %s",
        _artifact(KEY)["artifact_id"],
    ) == 1
    assert connector.result["zips"] == 1


def test_two_sessions_do_not_clobber_the_same_filename(origin: FakeOrigin) -> None:
    origin.listed_sessions = [1, 2]
    _seed_bills(1, 2, 3)
    connector = BillTextConnector(
        [CONGRESS],
        ("hr",),
        (1, 2),
        govinfo=origin,  # type: ignore[arg-type]
        downloader=origin.download,
        sleep=lambda _s: None,
    )
    run_connector(connector)

    assert _records() == 12
    keys = [
        row[0]
        for row in _rows(
            "SELECT source_key FROM core.document WHERE document_type = 'govinfo_bill_text' "
            "AND congress = 998 ORDER BY 1"
        )
    ]
    assert any(key.startswith("1/") for key in keys)
    assert any(key.startswith("2/") for key in keys)
    assert len(keys) == len(set(keys)) == 12


def test_download_only_registers_bytes_and_a_later_sync_loads_without_refetching(
    origin: FakeOrigin,
) -> None:
    _seed_bills(1, 2, 3)
    _sync(origin, download_only=True)
    assert _records() == 0 and _artifact()["status"] == "downloaded"

    _sync(origin)
    assert origin.downloads == [KEY] and _records() == 6 and _artifact()["status"] == "loaded"


def test_a_truncated_download_is_never_ingested(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    origin.truncate = True
    with pytest.raises(RuntimeError, match="reports"):
        _sync(origin)
    assert _records() == 0

    origin.truncate = False
    connector = _sync(origin)
    assert connector.result["items"][0]["reason"] == "retained size differs from the origin"
    assert _records() == 6


def test_a_malformed_member_is_skipped_and_the_zip_is_not_loaded(origin: FakeOrigin) -> None:
    origin.publish({**_members(range(1, 4), ("ih", "eh")), f"BILLS-{CONGRESS}hr9ih.xml": "<bill>"})
    _seed_bills(1, 2, 3, 9)
    connector = _sync(origin)

    assert _records() == 6
    assert connector.result["malformed_members"] == {KEY: [f"BILLS-{CONGRESS}hr9ih.xml"]}
    assert connector.result["partial"] is True and _run_status() == "partial"
    assert _artifact()["status"] == "downloaded"


def test_xml_that_contradicts_its_file_name_is_loaded_under_the_filename(
    origin: FakeOrigin,
) -> None:
    origin.publish({**_members([1], ("ih",)), f"BILLS-{CONGRESS}hr7ih.xml": _bills_xml(8)})
    _seed_bills(1, 7, 8)
    connector = _sync(origin)

    assert _records() == 2
    assert (
        _one(
            "SELECT count(*) AS n FROM core.bill_text_source_record "
            "WHERE congress = 998 AND bill_number = '7'"
        )
        == 1
    )
    assert (
        _one(
            "SELECT count(*) AS n FROM core.bill_text_source_record "
            "WHERE congress = 998 AND bill_number = '8'"
        )
        == 0
    )
    assert connector.result["malformed_members"] == {}
    assert connector.result["stale_dublin_core"] == 1
    assert connector.result["partial"] is False and _run_status() == "succeeded"
    assert _artifact()["status"] == "loaded"


def test_no_published_bills_congresses_is_a_clear_error_not_an_index_error(
    origin: FakeOrigin,
) -> None:
    origin.listed_congresses = []
    with pytest.raises(ValueError, match="no BILLS Congress"):
        _sync(origin)
    assert origin.downloads == []


def test_stored_records_equal_the_xml(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    _sync(origin)
    rows = _rows(
        "SELECT source_member, record FROM core.bill_text_source_record WHERE congress = 998"
    )
    for member, record in rows:
        root = parse_xml_without_dtd(origin.members[member].encode())
        assert record_problems(root, record) == []
        assert "T998001" in ElementTree.tostring(root, encoding="unicode")


def test_a_killed_load_resumes_from_recorded_members(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    with _die_on_save(3), pytest.raises(RuntimeError, match="killed"):
        _sync(origin, batch_size=2)

    assert _run_status() == "failed"
    already = _records()
    assert already == 2  # first batch committed

    _sync(origin, batch_size=2)
    assert _records() == 6
    assert origin.downloads == [KEY]


def test_a_second_sync_while_one_is_running_is_refused(origin: FakeOrigin) -> None:
    holder = connect()
    holder.autocommit = True
    holder.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (bill_text_mod.LOCK_KEY,))
    try:
        with pytest.raises(RuntimeError, match="another sync-bill-text"):
            _sync(origin)
    finally:
        holder.close()
    assert origin.downloads == []


def test_congresses_before_113_never_create_a_run() -> None:
    with pytest.raises(ValueError, match="starts at Congress 113"):
        BillTextConnector([112])
    assert _one("SELECT count(*) AS n FROM ingest.run WHERE dataset_id = 'congress.govinfo_bills'") == 0


def test_the_migration_refuses_to_downgrade_while_records_exist(origin: FakeOrigin) -> None:
    _seed_bills(1, 2, 3)
    _sync(origin)
    rows = _records()
    with pytest.raises(RuntimeError, match=rf"core\.bill_text_source_record holds {rows} rows"):
        command.downgrade(_alembic_config(), "c8e2a5f1b937")
    assert _one("SELECT version_num AS v FROM alembic_version") == "c9e4a1b27d83"
    assert _records() == rows
