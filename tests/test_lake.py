"""Story 9.4: the lake registry resolves moved folders, classifies everything, and touches nothing."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from opendiscourse_research import lake
from opendiscourse_research.config import PROJECT_ROOT, Settings
from opendiscourse_research.lake import (
    LakeError,
    LayoutError,
    format_inventory,
    inventory,
    load_layout,
    locate,
)


def _layout(tmp_path: Path, body: dict) -> lake.Layout:
    path = tmp_path / "layout.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "roots": {"a": {}, "b": {}}, **body}))
    return load_layout(path)


def _area(path: str, disposition: str = "keep", root: str = "a", kind: str = "raw") -> dict:
    return {"root": root, "path": path, "kind": kind, "disposition": disposition, "reason": "r"}


LOCATION = {
    "locations": {
        "thing": {
            "candidates": [
                {"root": "a", "path": "new/{year}/thing.zip"},
                {"root": "b", "path": "old/{year}/thing.zip"},
            ]
        }
    }
}


def test_locate_finds_the_legacy_copy_when_only_it_exists(tmp_path):
    layout = _layout(tmp_path, LOCATION)
    (tmp_path / "b" / "old" / "2020").mkdir(parents=True)
    (tmp_path / "b" / "old" / "2020" / "thing.zip").write_text("x")
    roots = {"a": tmp_path / "a", "b": tmp_path / "b"}
    assert locate("thing", roots=roots, layout=layout, year=2020) == (
        tmp_path / "b" / "old" / "2020" / "thing.zip"
    )


def test_first_existing_candidate_wins_when_a_folder_moved(tmp_path):
    layout = _layout(tmp_path, LOCATION)
    for root, folder in (("a", "new"), ("b", "old")):
        target = tmp_path / root / folder / "2020"
        target.mkdir(parents=True)
        (target / "thing.zip").write_text("x")
    roots = {"a": tmp_path / "a", "b": tmp_path / "b"}
    assert "new" in locate("thing", roots=roots, layout=layout, year=2020).parts


def test_unconfigured_root_yields_none_and_inventory_says_so(tmp_path):
    layout = _layout(tmp_path, {**LOCATION, "areas": [_area("x", root="b")]})
    roots = {"a": tmp_path / "a", "b": None}
    (tmp_path / "a").mkdir()
    assert locate("thing", roots=roots, layout=layout, year=1) is None
    assert inventory(layout=layout, roots=roots)["roots"]["b"]["status"] == "not_configured"


def test_missing_key_or_unknown_name_or_unsafe_value_is_an_actionable_error(tmp_path):
    layout = _layout(tmp_path, LOCATION)
    roots = {"a": tmp_path, "b": tmp_path}
    with pytest.raises(LakeError, match="year"):
        locate("thing", roots=roots, layout=layout)
    with pytest.raises(LakeError, match="Unknown"):
        locate("nope", roots=roots, layout=layout)
    with pytest.raises(LakeError, match="Unsafe"):
        locate("thing", roots=roots, layout=layout, year="../etc")


def test_unclassified_directories_are_reported_with_size(tmp_path):
    layout = _layout(tmp_path, {"areas": [_area("known")]})
    base = tmp_path / "a"
    (base / "known").mkdir(parents=True)
    (base / "mystery").mkdir()
    (base / "mystery" / "f.bin").write_bytes(b"12345")
    report = inventory(layout=layout, roots={"a": base, "b": None})
    assert [r["path"] for r in report["unclassified"]] == ["mystery"]
    assert report["unclassified"][0]["size_bytes"] == 5


def test_hold_areas_are_not_measured_or_descended(tmp_path):
    layout = _layout(tmp_path, {"areas": [_area("secret", "hold")]})
    base = tmp_path / "a"
    (base / "secret" / "deep").mkdir(parents=True)
    (base / "secret" / "deep" / "f").write_bytes(b"x" * 100)
    row = inventory(layout=layout, roots={"a": base, "b": None})["areas"][0]
    assert row["disposition"] == "hold" and row["size_bytes"] is None and row["files"] is None
    measured = inventory(layout=layout, roots={"a": base, "b": None}, measure_hold=True)
    assert measured["areas"][0]["size_bytes"] == 100


def test_symlinks_are_recorded_and_never_followed(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big").write_bytes(b"x" * 1000)
    base = tmp_path / "a"
    base.mkdir()
    os.symlink(outside, base / "linked")
    layout = _layout(tmp_path, {"areas": [_area("linked", kind="link")]})
    row = inventory(layout=layout, roots={"a": base, "b": None})["areas"][0]
    assert row["fs_kind"] == "link" and row["size_bytes"] is None
    assert row["link_target"] == str(outside)


def test_specific_area_beats_a_wildcard_and_wildcards_do_not_swallow_children(tmp_path):
    layout = _layout(
        tmp_path,
        {
            "areas": [
                _area("top/keepme/inner", "adopt"),
                _area("top/*", "review"),
                _area("data*", "hold"),
            ]
        },
    )
    base = tmp_path / "a"
    for rel in ("top/keepme/inner", "top/keepme/other", "top/loose", "data1", "data2"):
        (base / rel).mkdir(parents=True)
    report = inventory(layout=layout, roots={"a": base, "b": None})
    by_path = {r["path"]: r["disposition"] for r in report["areas"]}
    assert by_path == {
        "top/keepme/inner": "adopt",
        "top/loose": "review",
        "data1": "hold",
        "data2": "hold",
    }
    assert [r["path"] for r in report["unclassified"]] == ["top/keepme/other"]


def test_prune_areas_holding_registered_artifacts_are_flagged_as_conflicts(tmp_path):
    layout = _layout(tmp_path, {"areas": [_area("junk", "prune")]})
    base = tmp_path / "a"
    (base / "junk").mkdir(parents=True)
    (base / "junk" / "kept.zip").write_text("x")
    report = inventory(
        layout=layout, roots={"a": base, "b": None}, registered=[str(base / "junk" / "kept.zip")]
    )
    assert report["prune_conflicts"][0]["registered_artifacts"] == 1
    assert "PRUNE CONFLICTS" in format_inventory(report)


def test_the_scan_changes_nothing(tmp_path):
    layout = _layout(tmp_path, {"areas": [_area("x", "prune")]})
    base = tmp_path / "a"
    (base / "x").mkdir(parents=True)
    (base / "x" / "f").write_text("data")
    before = sorted(p.relative_to(base) for p in base.rglob("*"))
    inventory(layout=layout, roots={"a": base, "b": None})
    assert sorted(p.relative_to(base) for p in base.rglob("*")) == before
    assert (base / "x" / "f").read_text() == "data"


@pytest.mark.parametrize(
    "body,message",
    [
        ({"areas": [{**_area("/abs/path")}]}, "relative"),
        ({"areas": [{**_area("a/../b")}]}, "relative"),
        ({"areas": [{**_area("x", "vaporize")}]}, "disposition"),
        ({"areas": [{**_area("x", root="zzz")}]}, "unknown root"),
        ({"areas": [{**_area("x"), "reason": ""}]}, "reason"),
        ({"locations": {"t": {"candidates": [{"root": "a", "path": "/etc"}]}}}, "relative"),
    ],
)
def test_layout_validation_rejects_unsafe_or_incomplete_entries(tmp_path, body, message):
    with pytest.raises(LayoutError, match=message):
        _layout(tmp_path, body)


def test_the_shipped_layout_is_valid_and_machine_independent():
    layout = load_layout()
    assert {"active", "legacy", "project"} <= set(layout.roots)
    text = (PROJECT_ROOT / "inventory" / "lake_layout.yaml").read_text()
    assert "/mnt/" not in text and "/home/" not in text
    assert all(a.reason for a in layout.areas)


def test_relative_data_root_is_anchored_to_the_project_not_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    configured = Settings(data_root="./lake/raw", _env_file=None)
    assert configured.data_root == str(PROJECT_ROOT / "lake" / "raw")
    absolute = Settings(data_root="/somewhere/raw", legacy_lake_root="~/x", _env_file=None)
    assert absolute.data_root == "/somewhere/raw"
    assert not absolute.legacy_lake_root.startswith("~")
