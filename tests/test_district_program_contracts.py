"""Contract tests for the executable district/GIS programme."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load(path: str) -> dict[str, Any]:
    payload = yaml.safe_load((ROOT / path).read_text())
    assert isinstance(payload, dict), path
    return payload


def test_district_story_graph_is_valid() -> None:
    programme = _load("_bmad-output/specs/spec-district-linked-context/stories.yaml")
    stories = programme["stories"]
    assert isinstance(stories, list) and stories

    by_id = {str(story["id"]): story for story in stories}
    assert len(by_id) == len(stories)
    assert "10.6" in by_id

    allowed_status = {"planned", "blocked", "ready", "in_progress", "done"}
    for story_id, story in by_id.items():
        assert story["status"] in allowed_status, story_id
        dependencies = [str(value) for value in story.get("depends_on", [])]
        assert all(dependency in by_id for dependency in dependencies), story_id
        if story["status"] in {"ready", "in_progress", "done"}:
            assert all(by_id[dependency]["status"] == "done" for dependency in dependencies), story_id

    # The horizontal-source gate is not allowed to open before the vertical mart proof.
    assert by_id["10.6"]["gate"] == "v1_spine"
    assert by_id["10.7"]["gate"] == "slice_proven"


def test_geography_calendar_matches_first_vertical_slice() -> None:
    calendar = _load("inventory/geography-vintages.yaml")
    roadmap = _load("inventory/dataset-roadmap.yaml")

    releases = calendar["acs_5_releases"]
    assert releases[2021]["congressional_district_congress"] == 116
    assert releases[2024]["congressional_district_congress"] == 119
    assert releases[2024]["survey_window"] == [2020, 2024]

    first = roadmap["first_vertical_slice"]
    assert first["completion_story"] == "10.6"
    assert first["congress"] == releases[2024]["congressional_district_congress"]
    assert first["acs_5_release_year"] == 2024
    assert first["survey_window"] == releases[2024]["survey_window"]
    assert first["mart"] == "congressional_district_period"


def test_roadmap_ids_and_existing_catalog_links_are_consistent() -> None:
    roadmap = _load("inventory/dataset-roadmap.yaml")
    sources = _load("inventory/sources.yaml")

    datasets = roadmap["datasets"]
    roadmap_ids = [str(row["id"]) for row in datasets]
    assert len(roadmap_ids) == len(set(roadmap_ids))

    catalog_ids = {
        str(dataset["id"])
        for provider in sources["providers"]
        for dataset in provider.get("datasets", [])
    }
    for row in datasets:
        existing = row.get("existing")
        if existing is not None:
            assert str(existing) in catalog_ids, row["id"]


def test_heavy_tiger_expansion_is_not_authorized_in_first_slice() -> None:
    roadmap = _load("inventory/dataset-roadmap.yaml")
    by_id = {str(row["id"]): row for row in roadmap["datasets"]}

    assert by_id["census.tiger.cd"]["gate"] == "v1_spine"
    assert by_id["census.tiger.sldu"]["gate"] == "v1_spine"
    assert by_id["census.tiger.sldl"]["gate"] == "v1_spine"

    for dataset_id in (
        "census.tiger.tract",
        "census.tiger.block_group",
        "census.tiger.block",
        "census.tiger.puma",
    ):
        assert by_id[dataset_id]["gate"] != "v1_spine", dataset_id
