"""Regression tests for Census bulk plans, gates, and format mappings."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from opendiscourse_research.ingestion.bulk import advance_plan, approve_plan
from opendiscourse_research.ingestion.cbp_bulk import build_cbp_bulk_plan
from opendiscourse_research.ingestion.acs_bulk import build_acs5_bulk_plan
from opendiscourse_research.ingestion.dhc_bulk import build_dhc_bulk_plan
from opendiscourse_research.ingestion.dhc_load import _matrix, _scope as dhc_scope
from opendiscourse_research.ingestion.acs_load import _geo_id as acs_geo_id, _numeric as acs_numeric, _scope as acs_scope
from opendiscourse_research.ingestion.pep_bulk import build_pep_bulk_plan
from opendiscourse_research.ingestion.pep_load import _scope as pep_scope
from opendiscourse_research.ingestion.tiger_bulk import build_tiger_bulk_plan
from opendiscourse_research.ingestion.tiger_load import _scope as tiger_scope
from opendiscourse_research.browser import acs_package_tables


def resource(dataset_id: str, key: str, resource_type: str) -> dict[str, str]:
    return {"dataset_id": dataset_id, "resource_key": key, "resource_type": resource_type}


class TestCensusBulkPlans(unittest.TestCase):
    def test_reviewed_acs_housing_core_package_is_small_and_explicit(self) -> None:
        self.assertEqual(
            acs_package_tables(),
            ["B25001", "B25002", "B25003", "B25004", "B25010", "B25064", "B25077"],
        )
        with self.assertRaisesRegex(ValueError, "Unknown or invalid ACS package"):
            acs_package_tables("not-a-package")

    def test_acs_detailed_table_plan_uses_bulk_dataset_for_artifact_lineage(self) -> None:
        plan = build_acs5_bulk_plan(
            "test",
            [resource("census.acs_5", "2024:B25001", "Detailed Table")],
        )
        self.assertEqual(plan["dataset"], "census.acs_5_bulk")
        self.assertEqual(plan["artifacts"][-1]["artifact_key"], "acs5-2024-b25001")

    def test_cbp_plan_contains_complete_release_and_rejects_mixed_years(self) -> None:
        selected = [resource("census.business_patterns", "full:2023", "Complete CSV bundle")]
        plan = build_cbp_bulk_plan("test", selected)
        self.assertEqual(plan["state"], "draft")
        self.assertEqual(len(plan["artifacts"]), 10)
        with self.assertRaisesRegex(ValueError, "one CBP plan per release year"):
            build_cbp_bulk_plan("test", selected + [resource("census.business_patterns", "full:2022", "Complete CSV bundle")])

    def test_pep_plan_never_mixes_vintages(self) -> None:
        selected = [resource("census.population_estimates", "vintage:2025", "National, state, and county totals")]
        self.assertEqual(build_pep_bulk_plan("test", selected)["selection"]["vintage"], 2025)
        with self.assertRaisesRegex(ValueError, "exactly one PEP vintage"):
            build_pep_bulk_plan("test", selected + [resource("census.population_estimates", "vintage:2024", "National, state, and county totals")])

    def test_dhc_plan_includes_official_table_matrix(self) -> None:
        plan = build_dhc_bulk_plan("test", [resource("census.decennial", "dhc:2020:national", "Complete DHC national archive")])
        self.assertEqual([item["artifact_key"] for item in plan["artifacts"]], ["dhc-2020-national", "dhc-2020-table-matrix"])

    def test_tiger_plan_requires_exact_package(self) -> None:
        selected = [resource("census.tiger", "national:2020:core-boundaries", "National core boundary layers")]
        self.assertEqual(len(build_tiger_bulk_plan("test", selected)["artifacts"]), 4)
        with self.assertRaisesRegex(ValueError, "exactly"):
            build_tiger_bulk_plan("test", [])


class TestBulkLifecycle(unittest.TestCase):
    def test_approval_requires_successful_preview_and_records_explicit_scope(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "plan.yaml"
            path.write_text(yaml.safe_dump({"state": "draft", "artifacts": [{"artifact_key": "x"}], "storage": {}}))
            with self.assertRaisesRegex(ValueError, "No preflight"):
                approve_plan(path, {"geography_levels": ["county"]})
            path.with_suffix(".preview.json").write_text(json.dumps({"approved": True}))
            result = approve_plan(path, {"geography_levels": ["county"]})
            self.assertEqual(result["state"], "approved")
            self.assertEqual(result["canonical_load_scope"], {"geography_levels": ["county"]})
            self.assertEqual(result["storage"]["state"], "previewed")

    def test_lifecycle_transition_cannot_skip_or_repeat_a_phase(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "plan.yaml"
            path.write_text(yaml.safe_dump({"state": "downloaded"}))
            with self.assertRaisesRegex(ValueError, "must be 'staged'"):
                advance_plan(path, "staged", "loaded", "load", {})
            result = advance_plan(path, "downloaded", "staged", "staging", {"row_count": 2})
            self.assertEqual(result["state"], "staged")
            self.assertEqual(result["staging"]["row_count"], 2)


class TestCensusScopesAndMatrix(unittest.TestCase):
    def test_scopes_reject_empty_or_unsupported_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "DHC approval"):
            dhc_scope({"canonical_load_scope": {}})
        with self.assertRaisesRegex(ValueError, "supported PEP"):
            pep_scope({"canonical_load_scope": {"geography_levels": ["zip"]}})
        with self.assertRaisesRegex(ValueError, "supported TIGER"):
            tiger_scope({"canonical_load_scope": {"layers": ["block"]}})
        with self.assertRaisesRegex(ValueError, "supported ACS"):
            acs_scope({"canonical_load_scope": {"geography_types": ["tract"]}})

    def test_acs_geo_ids_only_admit_state_and_county(self) -> None:
        self.assertEqual(acs_geo_id("0400000US06"), ("state", "06"))
        self.assertEqual(acs_geo_id("0500000US06037"), ("county", "06037"))
        self.assertIsNone(acs_geo_id("0100000US"))
        self.assertIsNone(acs_geo_id("1400000US06037101100"))
        self.assertIsNone(acs_geo_id("0500000US0603"))

    def test_acs_numeric_cells_preserve_values_and_null_unavailable_markers(self) -> None:
        self.assertEqual(acs_numeric("123.45"), __import__("decimal").Decimal("123.45"))
        for value in (None, "", "N", ".", "-666666666", "-999999999"):
            self.assertIsNone(acs_numeric(value))
        with self.assertRaisesRegex(ValueError, "Invalid ACS numeric"):
            acs_numeric("not-a-number")

    def test_dhc_matrix_preserves_column_offsets_for_skipped_tables(self) -> None:
        import openpyxl
        with TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.xlsx"
            book = openpyxl.Workbook(); sheet = book.active; sheet.title = "DHC Table Matrix"
            sheet.append(["title"] * 4); sheet.append(["headers"] * 4)
            sheet.append([None, "P1", "P0010001", 5])
            sheet.append([None, "P1", "P0010002", 5])
            sheet.append([None, "H1", "H0010001", 5])
            book.save(path)
            self.assertEqual(_matrix(path, {"H1"}), {5: [("H1", "H0010001", 7)]})
