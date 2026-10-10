"""Schema contract for ``core.division_boundary`` and ``core.geography_crosswalk`` (Story 10.3, ADR-0006)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import pytest
from db_cluster import cloned_database
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.db import session
from opendiscourse_research.models.core import (
    division_boundary_table,
    division_table,
    geography_boundary_table,
    geography_crosswalk_table,
    geography_table,
)
from opendiscourse_research.repositories.legislation import register_artifact

pytestmark = pytest.mark.db

_RUN = uuid.uuid4().hex[:8]
CHECK_VIOLATION = "23514"
UNIQUE_VIOLATION = "23505"
NOT_NULL_VIOLATION = "23502"


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    """Use a private copy of the migrated PostGIS template."""
    with cloned_database():
        sync_inventory()
        yield


@contextmanager
def _rejects(constraint: str | None, sqlstate: str) -> Iterator[None]:
    """Expect an IntegrityError with this SQLSTATE and, when given, constraint name."""
    with pytest.raises(IntegrityError) as caught:
        yield
    assert caught.value.orig.sqlstate == sqlstate
    if constraint is not None:
        assert caught.value.orig.diag.constraint_name == constraint


def _artifact(suffix: str) -> uuid.UUID:
    return register_artifact(
        "census.tiger",
        f"https://example.test/{_RUN}-{suffix}.zip",
        f"/tmp/{_RUN}-{suffix}.zip",
        f"divbound-{_RUN}-{suffix}",
        metadata={"story": "10.3"},
    )["artifact_id"]


def _geography(suffix: str, geography_type: str = "congressional_district") -> uuid.UUID:
    table = geography_table()
    with session() as active:
        return active.execute(
            insert(table)
            .values(geography_type=f"{geography_type}-{_RUN}", geoid=f"{_RUN}-{suffix}")
            .returning(table.c.geography_id)
        ).scalar_one()


def _division(suffix: str, artifact_id: uuid.UUID) -> uuid.UUID:
    table = division_table()
    with session() as active:
        return active.execute(
            insert(table)
            .values(
                ocd_division_id=f"ocd-division/country:us/state:zz-{_RUN}/cd:{suffix}",
                label=suffix,
                classification="cd",
                source_artifact_id=artifact_id,
            )
            .returning(table.c.division_id)
        ).scalar_one()


def _boundary(geography_id: uuid.UUID, artifact_id: uuid.UUID, vintage: int = 2024) -> uuid.UUID:
    table = geography_boundary_table()
    with session() as active:
        return active.execute(
            insert(table)
            .values(
                geography_id=geography_id,
                boundary_vintage=vintage,
                geom="SRID=4326;POINT(-77.0 38.9)",
                source_artifact_id=artifact_id,
            )
            .returning(table.c.boundary_id)
        ).scalar_one()


def _link(**overrides: object) -> dict[str, object]:
    return {"relationship_kind": "legal_boundary", **overrides}


def _crosswalk(from_id: uuid.UUID, to_id: uuid.UUID, artifact_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "from_geography_id": from_id,
        "to_geography_id": to_id,
        "from_vintage": 2024,
        "to_vintage": 2020,
        "method": "relationship",
        "weight_type": "none",
        "source_dataset_id": "census.tiger",
        "source_artifact_id": artifact_id,
        "source_ordinal": 1,
    }
    values.update(overrides)
    return values


def test_division_boundary_accepts_a_valid_link_and_rejects_duplicates(catalog_database: None) -> None:
    artifact = _artifact("dup")
    division = _division("1", artifact)
    boundary = _boundary(_geography("cd1"), artifact)
    table = division_boundary_table()
    row = _link(
        division_id=division,
        boundary_id=boundary,
        congress=119,
        valid_from=date(2025, 1, 3),
        valid_to=date(2027, 1, 3),
        source_artifact_id=artifact,
    )
    with session() as active:
        active.execute(insert(table).values(**row))
    with _rejects(None, UNIQUE_VIOLATION), session() as active:
        active.execute(insert(table).values(**row))
    with session() as active:
        count = active.execute(
            select(func.count()).select_from(table).where(table.c.division_id == division)
        ).scalar_one()
    assert count == 1


def test_division_boundary_requires_source_artifact(catalog_database: None) -> None:
    artifact = _artifact("nosrc")
    division = _division("2", artifact)
    boundary = _boundary(_geography("cd2"), artifact)
    with _rejects(None, NOT_NULL_VIOLATION), session() as active:
        active.execute(
            insert(division_boundary_table()).values(
                **_link(division_id=division, boundary_id=boundary, source_artifact_id=None)
            )
        )


def test_division_boundary_validity_interval_must_be_ordered(catalog_database: None) -> None:
    artifact = _artifact("interval")
    division = _division("3", artifact)
    boundary = _boundary(_geography("cd3"), artifact)
    with _rejects("division_boundary_validity_check", CHECK_VIOLATION), session() as active:
        active.execute(
            insert(division_boundary_table()).values(
                **_link(
                    division_id=division,
                    boundary_id=boundary,
                    valid_from=date(2027, 1, 3),
                    valid_to=date(2025, 1, 3),
                    source_artifact_id=artifact,
                )
            )
        )


def test_crosswalk_unweighted_relationship_carries_no_weight(catalog_database: None) -> None:
    artifact = _artifact("xw-none")
    a, b = _geography("xw-a"), _geography("xw-b", "county")
    table = geography_crosswalk_table()
    with session() as active:
        active.execute(insert(table).values(**_crosswalk(a, b, artifact)))
    with _rejects("geography_crosswalk_weight_presence_check", CHECK_VIOLATION), session() as active:
        active.execute(insert(table).values(**_crosswalk(a, b, artifact, source_ordinal=2, weight=0.5)))


def test_crosswalk_weighted_row_requires_a_weight(catalog_database: None) -> None:
    artifact = _artifact("xw-weighted")
    a, b = _geography("xw-c"), _geography("xw-d", "county")
    table = geography_crosswalk_table()
    with _rejects("geography_crosswalk_weight_presence_check", CHECK_VIOLATION), session() as active:
        active.execute(
            insert(table).values(**_crosswalk(a, b, artifact, weight_type="population", method="population_weighted"))
        )
    with session() as active:
        active.execute(
            insert(table).values(
                **_crosswalk(
                    a, b, artifact, weight_type="population", method="population_weighted", weight=0.25, source_ordinal=3
                )
            )
        )


@pytest.mark.parametrize("column", ["weight", "coverage_ratio"])
@pytest.mark.parametrize("value", [-0.1, 1.2])
def test_crosswalk_weight_and_coverage_stay_in_unit_interval(catalog_database: None, column: str, value: float) -> None:
    artifact = _artifact(f"xw-range-{column}-{value}")
    a, b = _geography(f"xw-e-{column}-{value}"), _geography(f"xw-f-{column}-{value}", "county")
    extra: dict[str, object] = {column: value}
    if column == "weight":
        extra.update(weight_type="assignment", method="block_assignment")
    constraint = f"geography_crosswalk_{column}_range_check"
    with _rejects(constraint, CHECK_VIOLATION), session() as active:
        active.execute(insert(geography_crosswalk_table()).values(**_crosswalk(a, b, artifact, **extra)))


def test_crosswalk_rejects_unknown_weight_type(catalog_database: None) -> None:
    artifact = _artifact("xw-type")
    a, b = _geography("xw-g"), _geography("xw-h", "county")
    with _rejects("geography_crosswalk_weight_type_check", CHECK_VIOLATION), session() as active:
        active.execute(insert(geography_crosswalk_table()).values(**_crosswalk(a, b, artifact, weight_type="area_overlap", weight=0.5)))


@pytest.mark.parametrize("missing", ["source_artifact_id", "source_dataset_id", "from_vintage", "to_vintage", "method"])
def test_crosswalk_requires_provenance_and_vintages(catalog_database: None, missing: str) -> None:
    artifact = _artifact(f"xw-null-{missing}")
    a, b = _geography(f"xw-i-{missing}"), _geography(f"xw-j-{missing}", "county")
    with _rejects(None, NOT_NULL_VIOLATION), session() as active:
        active.execute(insert(geography_crosswalk_table()).values(**_crosswalk(a, b, artifact, **{missing: None})))


def test_crosswalk_rejects_duplicate_source_relation(catalog_database: None) -> None:
    artifact = _artifact("xw-dup")
    a, b = _geography("xw-k"), _geography("xw-l", "county")
    table = geography_crosswalk_table()
    row = _crosswalk(a, b, artifact)
    with session() as active:
        active.execute(insert(table).values(**row))
    with _rejects("geography_crosswalk_source_key", UNIQUE_VIOLATION), session() as active:
        active.execute(insert(table).values(**row))
