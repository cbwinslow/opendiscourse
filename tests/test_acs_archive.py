"""Archive-manifest rules for ACS PUMS and AHS (no network or database)."""

import json

import pytest
import respx
from httpx import Response

from opendiscourse_research.ingestion.acs_archive import (
    ACS_1_YEAR,
    ACS_5_YEAR,
    ACSArchiveConnector,
    _pums_record_type,
    capacity_manifest,
    main,
    manifest_from_index,
    publisher_gaps,
)
from opendiscourse_research.ingestion.connector import (
    Connector,
    ConnectorContext,
    run_connector,
)
from opendiscourse_research.providers.census import (
    ArchiveIndex,
    census_directory_links,
    discover_archive_index,
    official_housing_archive_indexes,
)


def _entry(**overrides):
    value = {"product": "acs_pums_1", "period": "2024", "component": "us", "kind": "data", "url": "https://www2.census.gov/x.zip", "bytes": 12}
    value.update(overrides)
    return value


def test_standard_acs_ranges_and_publisher_gaps_are_explicit():
    assert 2020 not in ACS_1_YEAR and ACS_1_YEAR[0] == 2005
    assert ACS_5_YEAR == tuple(range(2009, 2025))
    assert {gap["period"] for gap in publisher_gaps()} >= {"2020", "2000-2004", "2000"}


def test_pums_member_type_handles_current_and_legacy_csv_names():
    assert _pums_record_type("psam_pusa.csv") == "person"
    assert _pums_record_type("csv_pus.csv") == "person"
    assert _pums_record_type("psam_husa.csv") == "housing"
    assert _pums_record_type("csv_hus.csv") == "housing"


def test_official_index_factory_covers_every_available_pums_and_ahs_release():
    indexes = official_housing_archive_indexes()
    identities = {(index.product, index.period) for index in indexes}
    assert ("acs_pums_1", "2005") in identities
    assert ("acs_pums_1", "2020") not in identities
    assert ("acs_pums_5", "2005-2009") in identities
    assert ("acs_pums_5", "2020-2024") in identities
    assert ("ahs", "2001") in identities and ("ahs", "2023") in identities
    assert ("ahs", "2002") in identities and ("ahs", "2013") in identities
    assert ("ahs", "2006") not in identities and ("ahs", "2012") not in identities


def test_official_index_factory_uses_census_legacy_pums_layout_before_2009():
    indexes = {
        (index.product, index.period): index.url
        for index in official_housing_archive_indexes()
    }
    base = "https://www2.census.gov/programs-surveys/acs/data/pums"
    assert indexes[("acs_pums_1", "2005")] == f"{base}/2005/"
    assert indexes[("acs_pums_1", "2008")] == f"{base}/2008/"
    assert indexes[("acs_pums_1", "2009")] == f"{base}/2009/1-Year/"
    assert indexes[("acs_pums_5", "2005-2009")] == f"{base}/2009/5-Year/"


def test_ahs_current_relational_is_the_only_publishable_representation():
    artifacts = manifest_from_index([
        _entry(product="ahs", period="2023", component="national", representation="relational"),
        _entry(product="ahs", period="2023", component="national", representation="flat", version="superseded", url="https://www2.census.gov/old.zip"),
    ])
    assert [artifact.selected for artifact in artifacts] == [True, False]
    with pytest.raises(ValueError, match="duplicate AHS"):
        manifest_from_index([_entry(product="ahs"), _entry(product="ahs", url="https://www2.census.gov/y.zip")])


def test_multiple_release_documents_are_distinct_retained_artifacts():
    artifacts = manifest_from_index(
        [
            _entry(kind="dictionary", url="https://www2.census.gov/dictionary.pdf"),
            _entry(kind="dictionary", url="https://www2.census.gov/labels.pdf"),
        ]
    )
    assert len({artifact.artifact_key for artifact in artifacts}) == 2


def test_unknown_size_is_rejected_before_capacity_approval():
    with pytest.raises(ValueError, match="unknown byte size"):
        manifest_from_index([_entry(bytes=None)])


def test_connector_obeys_protocol_and_capacity_failure_checkpoints(monkeypatch):
    connector = ACSArchiveConnector([_entry()])
    assert isinstance(connector, Connector)
    monkeypatch.setattr("opendiscourse_research.ingestion.acs_archive.storage_preview", lambda *_a, **_k: {"approved": False, "reason": "insufficient capacity", "artifacts": []})
    with pytest.raises(RuntimeError, match="capacity gate"):
        run_connector(connector, ConnectorContext(source_id=connector.source_id))


def test_transfer_requires_separate_operator_approval(monkeypatch):
    connector = ACSArchiveConnector([_entry()])
    monkeypatch.setattr(
        "opendiscourse_research.ingestion.acs_archive.storage_preview",
        lambda *_a, **_k: {"approved": True, "reason": "enough capacity", "artifacts": []},
    )
    with pytest.raises(RuntimeError, match="transfer-approved"):
        run_connector(connector)


def test_capacity_manifest_has_selected_artifacts_and_gaps(monkeypatch):
    artifacts = manifest_from_index([_entry()])
    monkeypatch.setattr("opendiscourse_research.ingestion.acs_archive.storage_preview", lambda *_a, **_k: {"approved": True})
    assert capacity_manifest(artifacts)["gaps"] == publisher_gaps()


def test_preflight_command_prints_manifest_without_starting_transfer(monkeypatch, capsys):
    monkeypatch.setattr(
        "opendiscourse_research.ingestion.acs_archive.official_housing_archive_indexes",
        lambda: (),
    )
    monkeypatch.setattr(
        "opendiscourse_research.ingestion.acs_archive.capacity_manifest",
        lambda _artifacts: {"approved": True, "reason": "enough capacity", "artifacts": [], "gaps": []},
    )
    assert main(["--all-official-indexes"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "approved": True,
        "artifacts": [],
        "gaps": [],
        "reason": "enough capacity",
    }


def test_census_directory_parser_keeps_only_official_child_links():
    links = census_directory_links(
        "https://www2.census.gov/programs-surveys/acs/pums/2024/",
        '<a href="data.zip">data</a><a href="../">up</a><a href="https://bad.example/x">bad</a>',
    )
    assert links == ["https://www2.census.gov/programs-surveys/acs/pums/2024/data.zip"]


@respx.mock
def test_official_index_discovery_keeps_publisher_bytes_and_documents():
    index_url = "https://www2.census.gov/archive/"
    data_url = "https://www2.census.gov/archive/csv_pus.zip"
    notes_url = "https://www2.census.gov/archive/notes.pdf"
    respx.get(index_url).mock(
        return_value=Response(200, text='<a href="csv_pus.zip">data</a><a href="notes.pdf">notes</a>')
    )
    respx.head(data_url).mock(return_value=Response(200, headers={"content-length": "12"}))
    respx.head(notes_url).mock(return_value=Response(200, headers={"content-length": "34"}))
    entries = discover_archive_index(ArchiveIndex(index_url, "acs_pums_1", "2024", "us"))
    assert {(entry["kind"], entry["bytes"]) for entry in entries} == {
        ("data", 12),
        ("documentation", 34),
    }


@respx.mock
def test_official_index_discovery_uses_one_byte_range_when_head_omits_size():
    index_url = "https://www2.census.gov/archive/"
    data_url = "https://www2.census.gov/archive/csv_pus.zip"
    respx.get(index_url).mock(return_value=Response(200, text='<a href="csv_pus.zip">data</a>'))
    respx.head(data_url).mock(return_value=Response(200))
    respx.get(data_url, headers={"Range": "bytes=0-0"}).mock(
        return_value=Response(206, headers={"content-range": "bytes 0-0/123"})
    )
    entries = discover_archive_index(ArchiveIndex(index_url, "acs_pums_1", "2024", "us"))
    assert entries[0]["bytes"] == 123


@respx.mock
def test_ahs_discovery_selects_only_latest_relational_csv_per_sample():
    index_url = "https://www2.census.gov/programs-surveys/ahs/2023/"
    v10 = f"{index_url}AHS%202023%20National%20PUF%20v1.0%20CSV.zip"
    v11 = f"{index_url}AHS%202023%20National%20PUF%20v1.1%20CSV.zip"
    flat = f"{index_url}AHS%202023%20National%20PUF%20v1.1%20Flat%20CSV.zip"
    respx.get(index_url).mock(return_value=Response(200, text=(
        '<a href="AHS%202023%20National%20PUF%20v1.0%20CSV.zip">v1</a>'
        '<a href="AHS%202023%20National%20PUF%20v1.1%20CSV.zip">v2</a>'
        '<a href="AHS%202023%20National%20PUF%20v1.1%20Flat%20CSV.zip">flat</a>'
    )))
    for url in (v10, v11, flat):
        respx.head(url).mock(return_value=Response(200, headers={"content-length": "12"}))
    entries = discover_archive_index(ArchiveIndex(index_url, "ahs", "2023", "all"))
    artifacts = manifest_from_index(entries)
    selected = [artifact for artifact in artifacts if artifact.selected]
    assert len(artifacts) == 3
    assert len(selected) == 1 and selected[0].version == "current"


@respx.mock
def test_ahs_discovery_excludes_sas_package_from_csv_record_selection():
    index_url = "https://www2.census.gov/programs-surveys/ahs/2001/"
    csv_url = f"{index_url}AHS%202001%20National%20PUF%20v2.0%20CSV.zip"
    sas_url = f"{index_url}AHS%202001%20National%20PUF%20v2.0%20SAS.zip"
    respx.get(index_url).mock(return_value=Response(200, text=(
        '<a href="AHS%202001%20National%20PUF%20v2.0%20CSV.zip">csv</a>'
        '<a href="AHS%202001%20National%20PUF%20v2.0%20SAS.zip">sas</a>'
    )))
    respx.head(csv_url).mock(return_value=Response(200, headers={"content-length": "12"}))
    entries = discover_archive_index(ArchiveIndex(index_url, "ahs", "2001", "all"))
    assert [entry["url"] for entry in entries] == [csv_url]
