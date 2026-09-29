"""Archive-manifest rules for ACS PUMS and AHS (no network or database)."""

import json
from contextlib import contextmanager

import pytest
import respx
import httpx
from httpx import Response
from typer.testing import CliRunner

from opendiscourse_research.ingestion import bulk
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
    verified_acs_archive_fallback,
    verified_acs_archive_fallback_size,
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
    assert _pums_record_type("ss05pnj.csv") == "person"
    assert _pums_record_type("ss06pnj.csv") == "person"
    assert _pums_record_type("psam_husa.csv") == "housing"
    assert _pums_record_type("csv_hus.csv") == "housing"
    assert _pums_record_type("ss05hnj.csv") == "housing"
    assert _pums_record_type("ss06hnj.csv") == "housing"
    with pytest.raises(ValueError, match="unrecognised PUMS CSV member type"):
        _pums_record_type("ssxypnj.csv")


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


def test_retryable_primary_is_retried_before_verified_fallback(monkeypatch, tmp_path):
    connector = ACSArchiveConnector([_entry()], transfer_approved=True)
    ctx = connector.select(connector.discover(ConnectorContext(source_id=connector.source_id)))
    calls = []

    def transfer(spec, **_kwargs):
        calls.append(spec)
        if spec.url == "https://www2.census.gov/x.zip":
            raise ValueError("https://www2.census.gov/x.zip returned HTML content-type for a non-HTML artifact")
        return tmp_path / "retained.zip"

    monkeypatch.setattr("opendiscourse_research.ingestion.acs_archive.download_retrying", transfer)
    discarded = []
    monkeypatch.setattr("opendiscourse_research.ingestion.acs_archive.discard_partial", discarded.append)
    monkeypatch.setattr(
        "opendiscourse_research.ingestion.acs_archive.verified_acs_archive_fallback",
        lambda url, size: "https://www2.census.gov/equivalent.zip?download=1" if (url, size) == ("https://www2.census.gov/x.zip", 12) else None,
    )
    connector.extract(ctx)
    assert [call.url for call in calls] == [
        "https://www2.census.gov/x.zip",
        "https://www2.census.gov/equivalent.zip?download=1",
    ]
    assert calls[1].artifact_key == calls[0].artifact_key
    assert calls[1].metadata["fallback_from"] == calls[0].url
    assert "returned HTML content-type" in calls[1].metadata["fallback_error"]
    assert calls[1].metadata["fallback_verified_bytes"] == 12
    assert discarded == [calls[0]]
    assert calls[0].expected_bytes == calls[1].expected_bytes == 12
    assert calls[0].allowed_hosts == calls[1].allowed_hosts == ("www2.census.gov",)


def test_unsafe_fallback_fails_closed_after_primary_retries(monkeypatch):
    connector = ACSArchiveConnector([_entry()], transfer_approved=True)
    ctx = connector.select(connector.discover(ConnectorContext(source_id=connector.source_id)))
    calls = []

    def failed_transfer(spec, **_kwargs):
        calls.append(spec.url)
        raise ValueError("https://www2.census.gov/x.zip returned HTML content-type for a non-HTML artifact")

    monkeypatch.setattr("opendiscourse_research.ingestion.acs_archive.download_retrying", failed_transfer)
    monkeypatch.setattr("opendiscourse_research.ingestion.acs_archive.verified_acs_archive_fallback", lambda *_args: None)
    with pytest.raises(RuntimeError, match="no verified Census fallback"):
        connector.extract(ctx)
    assert calls == ["https://www2.census.gov/x.zip"]


def test_bounded_retry_records_attempt_context_before_success(monkeypatch, tmp_path):
    spec = bulk.ArtifactSpec("census.acs_housing_archive", "logical", "https://www2.census.gov/x.zip", "x.zip")
    calls = []

    def transfer(attempt, **_kwargs):
        calls.append(attempt)
        if len(calls) < 3:
            raise ValueError("https://www2.census.gov/x.zip returned HTML content-type for a non-HTML artifact")
        return tmp_path / "retained.zip"

    monkeypatch.setattr(bulk, "download", transfer)
    assert bulk.download_retrying(spec, backoff_seconds=0, sleep=lambda _delay: None) == tmp_path / "retained.zip"
    assert [item.metadata["transfer_attempt"] for item in calls] == [1, 2, 3]
    assert all(item.metadata["transfer_attempts"] == 3 for item in calls)


def test_temporary_transport_and_http_responses_are_retryable():
    request = httpx.Request("GET", "https://www2.census.gov/x.zip")
    for status in (408, 429, 503):
        assert bulk.retryable_download_error(
            httpx.HTTPStatusError("temporary", request=request, response=httpx.Response(status, request=request))
        )
    assert bulk.retryable_download_error(httpx.ConnectError("dropped", request=request))
    assert not bulk.retryable_download_error(
        httpx.HTTPStatusError("not found", request=request, response=httpx.Response(404, request=request))
    )


def test_zip_download_refuses_equal_sized_non_zip_response(monkeypatch, tmp_path):
    spec = bulk.ArtifactSpec(
        "census.acs_housing_archive",
        "logical",
        "https://www2.census.gov/fallback.zip",
        "2013/fallback.zip",
        expected_bytes=10,
    )
    target = tmp_path / "fallback.zip"
    request = httpx.Request("GET", spec.url)
    monkeypatch.setattr(bulk, "artifact_path", lambda _spec: target)
    monkeypatch.setattr(bulk, "get_artifact", lambda *_args: None)
    monkeypatch.setattr(bulk, "_upsert", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        bulk,
        "client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    content=b"same-size!",
                    headers={"content-type": "text/plain"},
                    request=request,
                )
            )
        ),
    )

    with pytest.raises(ValueError, match="non-ZIP content-type"):
        bulk._download_locked(spec, overwrite=False, chunk_size=3)

    assert not target.exists()
    assert not target.with_suffix(".zip.part").exists()


@respx.mock
def test_census_fallback_uses_only_verified_legacy_2013_census_path():
    primary = "https://www2.census.gov/programs-surveys/acs/data/pums/2013/5-Year/csv_pdc.zip"
    fallback = "https://www2.census.gov/acs2013_5yr/pums/csv_pdc.zip"
    route = respx.get(fallback).mock(
        return_value=Response(
            206,
            headers={
                "content-type": "application/zip",
                "content-range": "bytes 0-0/5157739",
            },
        )
    )
    assert verified_acs_archive_fallback(primary, 5157739) == fallback
    assert route.called


@respx.mock
def test_census_fallback_refuses_unverified_urls_sizes_and_content():
    assert verified_acs_archive_fallback("https://mirror.example/data.zip", 12) is None
    assert verified_acs_archive_fallback("https://www2.census.gov/data.zip", None) is None
    primary = "https://www2.census.gov/programs-surveys/acs/data/pums/2013/5-Year/csv_pdc.zip"
    fallback = "https://www2.census.gov/acs2013_5yr/pums/csv_pdc.zip"
    respx.get(fallback).mock(
        return_value=Response(
            206,
            headers={"content-type": "text/html", "content-range": "bytes 0-0/5157739"},
        )
    )
    assert verified_acs_archive_fallback(primary, 5157739) is None


@pytest.mark.parametrize(
    "primary_headers",
    [
        {"content-type": "text/html", "content-length": "247"},
        {"content-type": "text/plain", "content-length": "247"},
        {"content-type": "application/json", "content-length": "247"},
        {"content-type": "application/zip", "content-length": "0"},
    ],
)
@respx.mock
def test_untrusted_primary_zip_size_recovers_from_the_verified_census_alternate(primary_headers):
    index_url = "https://www2.census.gov/programs-surveys/acs/data/pums/2013/5-Year/"
    primary = f"{index_url}csv_pdc.zip"
    alternate = "https://www2.census.gov/acs2013_5yr/pums/csv_pdc.zip"
    respx.get(index_url).mock(return_value=Response(200, text='<a href="csv_pdc.zip">data</a>'))
    respx.head(primary).mock(
        return_value=Response(200, headers=primary_headers)
    )
    alternate_probe = respx.get(alternate, headers={"Range": "bytes=0-0"}).mock(
        return_value=Response(
            206,
            headers={"content-type": "application/zip", "content-range": "bytes 0-0/5157739"},
        )
    )

    entries = discover_archive_index(ArchiveIndex(index_url, "acs_pums_5", "2009-2013", "all"))

    assert entries == [{
        "product": "acs_pums_5", "period": "2009-2013", "component": "all",
        "kind": "data", "url": primary, "bytes": 5157739, "version": "current",
    }]
    assert alternate_probe.called


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ({"content-type": "application/xhtml+xml", "content-range": "bytes 0-0/247"}, 206),
        ({"content-type": "application/octet-stream", "content-range": "bytes 0-0/5157739"}, 206),
        ({"content-type": "text/plain", "content-range": "bytes 0-0/5157739"}, 206),
        ({"content-type": "application/zip"}, 206),
        ({"content-type": "application/zip", "content-range": "bytes 0-0/0"}, 206),
        ({"content-type": "application/zip", "content-range": "bytes 0-0/5157739"}, 200),
    ],
)
@respx.mock
def test_census_fallback_size_refuses_unsafe_range_responses(headers, status):
    primary = "https://www2.census.gov/programs-surveys/acs/data/pums/2013/5-Year/csv_pdc.zip"
    fallback = "https://www2.census.gov/acs2013_5yr/pums/csv_pdc.zip"
    respx.get(fallback).mock(return_value=Response(status, headers=headers))
    assert verified_acs_archive_fallback_size(primary) is None


@respx.mock
def test_html_primary_and_unsafe_alternate_leaves_size_unknown():
    index_url = "https://www2.census.gov/programs-surveys/acs/data/pums/2013/5-Year/"
    primary = f"{index_url}csv_pdc.zip"
    alternate = "https://www2.census.gov/acs2013_5yr/pums/csv_pdc.zip"
    respx.get(index_url).mock(return_value=Response(200, text='<a href="csv_pdc.zip">data</a>'))
    respx.head(primary).mock(return_value=Response(200))
    respx.get(primary, headers={"Range": "bytes=0-0"}).mock(
        return_value=Response(
            206,
            headers={"content-type": "application/xhtml+xml", "content-range": "bytes 0-0/247"},
        )
    )
    respx.get(alternate, headers={"Range": "bytes=0-0"}).mock(
        return_value=Response(206, headers={"content-type": "text/html", "content-range": "bytes 0-0/247"})
    )

    entries = discover_archive_index(ArchiveIndex(index_url, "acs_pums_5", "2009-2013", "all"))

    assert entries[0]["url"] == primary
    assert entries[0]["bytes"] is None


@pytest.mark.parametrize(
    "final_url",
    [
        "http://www2.census.gov/acs2013_5yr/pums/csv_pdc.zip",
        "https://mirror.example/acs2013_5yr/pums/csv_pdc.zip",
    ],
)
def test_census_fallback_size_refuses_non_census_or_non_https_final_response(
    monkeypatch, final_url
):
    primary = "https://www2.census.gov/programs-surveys/acs/data/pums/2013/5-Year/csv_pdc.zip"

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @contextmanager
        def stream(self, *_args, **_kwargs):
            yield Response(
                206,
                headers={"content-type": "application/zip", "content-range": "bytes 0-0/5157739"},
                request=httpx.Request("GET", final_url),
            )

    monkeypatch.setattr("opendiscourse_research.providers.census.client", FakeClient)
    assert verified_acs_archive_fallback_size(primary) is None


def test_source_status_command_rejects_unknown_contract(monkeypatch):
    from opendiscourse_research import cli

    monkeypatch.setattr(
        cli,
        "source_status",
        lambda _dataset: (_ for _ in ()).throw(ValueError("Expected one source contract for dataset 'unknown', found 0")),
    )
    result = CliRunner().invoke(cli.app, ["source-status", "unknown"])
    assert result.exit_code != 0
    assert "Expected one source contract" in result.output


def test_source_status_command_emits_required_json_fields(monkeypatch):
    from opendiscourse_research import cli

    report = {
        "dataset": "census.acs_housing_archive",
        "contract": {"selection": {}, "gaps": []},
        "artifacts": {"usable": [], "failures": [], "retained_bytes": 0},
        "stage": {"acs_pums_rows": 0, "ahs_rows": 0},
        "published": {"releases": 0, "projection_rows": 0},
    }
    monkeypatch.setattr(cli, "source_status", lambda dataset: report if dataset == report["dataset"] else None)
    result = CliRunner().invoke(cli.app, ["source-status", "census.acs_housing_archive"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload) == {"dataset", "contract", "artifacts", "stage", "published"}
    assert {"selection", "gaps"} <= set(payload["contract"])
    assert {"usable", "failures", "retained_bytes"} <= set(payload["artifacts"])


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
    respx.head(data_url).mock(return_value=Response(200, headers={"content-type": "application/zip", "content-length": "12"}))
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
        return_value=Response(206, headers={"content-type": "application/zip", "content-range": "bytes 0-0/123"})
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
        respx.head(url).mock(return_value=Response(200, headers={"content-type": "application/zip", "content-length": "12"}))
    entries = discover_archive_index(ArchiveIndex(index_url, "ahs", "2023", "all"))
    artifacts = manifest_from_index(entries)
    selected = [artifact for artifact in artifacts if artifact.selected]
    assert len(artifacts) == 3
    assert len(selected) == 1 and selected[0].version == "current"


@respx.mock
def test_ahs_discovery_excludes_sas_package_from_csv_record_selection():
    index_url = "https://www2.census.gov/programs-surveys/ahs/2001/"
    csv_url = f"{index_url}AHS%202001%20National%20PUF%20v2.0%20CSV.zip"
    respx.get(index_url).mock(return_value=Response(200, text=(
        '<a href="AHS%202001%20National%20PUF%20v2.0%20CSV.zip">csv</a>'
        '<a href="AHS%202001%20National%20PUF%20v2.0%20SAS.zip">sas</a>'
    )))
    respx.head(csv_url).mock(return_value=Response(200, headers={"content-type": "application/zip", "content-length": "12"}))
    entries = discover_archive_index(ArchiveIndex(index_url, "ahs", "2001", "all"))
    assert [entry["url"] for entry in entries] == [csv_url]
