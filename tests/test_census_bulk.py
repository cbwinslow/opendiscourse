"""Regression tests for Census bulk plans, gates, and format mappings."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml

from opendiscourse_research.browser import acs_package_tables
from opendiscourse_research.capacity import RemoteObject
from opendiscourse_research.ingestion.acs_bulk import (
    build_acs5_bulk_plan,
    preview_acs5_bulk_plan,
)
from opendiscourse_research.ingestion.acs_load import _geo_id as acs_geo_id
from opendiscourse_research.ingestion.acs_load import _numeric as acs_numeric
from opendiscourse_research.ingestion.acs_load import _scope as acs_scope
from opendiscourse_research.ingestion.acs_load import _table_id_partitions
from opendiscourse_research.ingestion.bulk import advance_plan, approve_plan
from opendiscourse_research.ingestion.cbp_bulk import build_cbp_bulk_plan
from opendiscourse_research.ingestion.census import relevant_acs_tables
from opendiscourse_research.ingestion.dhc_bulk import build_dhc_bulk_plan
from opendiscourse_research.ingestion.dhc_load import _matrix
from opendiscourse_research.ingestion.dhc_load import _scope as dhc_scope
from opendiscourse_research.ingestion.pep_bulk import build_pep_bulk_plan
from opendiscourse_research.ingestion.pep_load import _scope as pep_scope
from opendiscourse_research.ingestion.tiger_bulk import (
    build_tiger_bulk_plan,
    tiger_layers,
)
from opendiscourse_research.ingestion.tiger_load import _scope as tiger_scope


def resource(dataset_id: str, key: str, resource_type: str) -> dict[str, str]:
    return {
        "dataset_id": dataset_id,
        "resource_key": key,
        "resource_type": resource_type,
    }


class TestCensusBulkPlans(unittest.TestCase):
    def test_reviewed_acs_housing_core_package_is_small_and_explicit(self) -> None:
        self.assertEqual(
            acs_package_tables(),
            ["B25001", "B25002", "B25003", "B25004", "B25010", "B25064", "B25077"],
        )
        self.assertEqual(
            acs_package_tables("housing_extended"),
            ["B25034", "B25035", "B25070", "B25071", "B25075", "B25081", "B25093"],
        )
        with self.assertRaisesRegex(ValueError, "Unknown or invalid ACS package"):
            acs_package_tables("not-a-package")

    def test_acs_detailed_table_plan_uses_bulk_dataset_for_artifact_lineage(
        self,
    ) -> None:
        plan = build_acs5_bulk_plan(
            "test",
            [resource("census.acs_5", "2024:B25001", "Detailed Table")],
        )
        self.assertEqual(plan["dataset"], "census.acs_5_bulk")
        self.assertEqual(plan["artifacts"][-1]["artifact_key"], "acs5-2024-b25001")
        self.assertIn("acs-bulk-stage", plan["next"][-1])

    def test_acs_bulk_dataset_plan_passes_preflight_contract_check(self) -> None:
        plan = build_acs5_bulk_plan(
            "test", [resource("census.acs_5", "2024:B25001", "Detailed Table")]
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "acs.yaml"
            path.write_text(yaml.safe_dump(plan, sort_keys=False))
            with patch(
                "opendiscourse_research.ingestion.acs_bulk.remote_size",
                return_value=RemoteObject("https://example.test/acs", 1),
            ):
                report = preview_acs5_bulk_plan(path)
        self.assertTrue(report["approved"])

    def test_cbp_plan_contains_complete_release_and_rejects_mixed_years(self) -> None:
        selected = [
            resource("census.business_patterns", "full:2023", "Complete CSV bundle")
        ]
        plan = build_cbp_bulk_plan("test", selected)
        self.assertEqual(plan["state"], "draft")
        self.assertEqual(len(plan["artifacts"]), 8)
        with self.assertRaisesRegex(ValueError, "one CBP plan per release year"):
            build_cbp_bulk_plan(
                "test",
                selected
                + [
                    resource(
                        "census.business_patterns", "full:2022", "Complete CSV bundle"
                    )
                ],
            )

    def test_cbp_plan_uses_the_requested_years_own_filenames(self) -> None:
        selected = [
            resource("census.business_patterns", "full:2015", "Complete CSV bundle")
        ]
        plan = build_cbp_bulk_plan("test", selected)
        urls = [artifact["url"] for artifact in plan["artifacts"]]
        self.assertTrue(any(url.endswith("cbp15co.zip") for url in urls))
        self.assertFalse(any("cbp23" in url for url in urls))

    def test_pep_plan_never_mixes_vintages(self) -> None:
        selected = [
            resource(
                "census.population_estimates",
                "vintage:2020-2025",
                "National, state, and county totals",
            )
        ]
        plan = build_pep_bulk_plan("test", selected)
        self.assertEqual(plan["selection"]["vintage"], "2020-2025")
        self.assertEqual(plan["selection"]["release_year"], 2025)
        with self.assertRaisesRegex(ValueError, "exactly one PEP vintage"):
            build_pep_bulk_plan(
                "test",
                selected
                + [
                    resource(
                        "census.population_estimates",
                        "vintage:2010-2020",
                        "National, state, and county totals",
                    )
                ],
            )

    def test_pep_plan_uses_the_correct_filename_casing_per_vintage_series(self) -> None:
        current = build_pep_bulk_plan(
            "test",
            [
                resource(
                    "census.population_estimates",
                    "vintage:2020-2025",
                    "National, state, and county totals",
                )
            ],
        )
        legacy = build_pep_bulk_plan(
            "test",
            [
                resource(
                    "census.population_estimates",
                    "vintage:2010-2020",
                    "National, state, and county totals",
                )
            ],
        )
        self.assertTrue(
            current["artifacts"][0]["url"].endswith("NST-EST2025-ALLDATA.csv")
        )
        self.assertTrue(
            legacy["artifacts"][0]["url"].endswith("nst-est2020-alldata.csv")
        )

    def test_dhc_plan_includes_official_table_matrix(self) -> None:
        plan = build_dhc_bulk_plan(
            "test",
            [
                resource(
                    "census.decennial",
                    "dhc:2020:national",
                    "Complete DHC national archive",
                )
            ],
        )
        self.assertEqual(
            [item["artifact_key"] for item in plan["artifacts"]],
            ["dhc-2020-national", "dhc-2020-table-matrix"],
        )

    def test_tiger_plan_requires_exact_package(self) -> None:
        selected = [
            resource(
                "census.tiger",
                "national:2020:core-boundaries",
                "National core boundary layers",
            )
        ]
        self.assertEqual(len(build_tiger_bulk_plan("test", selected)["artifacts"]), 4)
        with self.assertRaisesRegex(ValueError, "exactly"):
            build_tiger_bulk_plan("test", [])

    def test_relevant_acs_tables_excludes_flags_collapsed_and_one_year_only(
        self,
    ) -> None:
        manifest = {
            "tables": [
                {
                    "id": "B01001",
                    "product": "Detailed Table",
                    "year": "1,5",
                },  # base -- kept
                {
                    "id": "B01001A",
                    "product": "Detailed Table",
                    "year": "1,5",
                },  # race iteration -- kept (genuine cross-tab, not redundant)
                {
                    "id": "C01001",
                    "product": "Detailed Table",
                    "year": "1,5",
                },  # collapsed dup -- dropped (redundant with the B-table)
                {
                    "id": "B98001",
                    "product": "Detailed Table",
                    "year": "1,5",
                },  # quality measure -- dropped (no substantive data)
                {
                    "id": "B99001",
                    "product": "Detailed Table",
                    "year": "1,5",
                },  # allocation flag -- dropped (no substantive data)
                {
                    "id": "B13002",
                    "product": "Detailed Table",
                    "year": "1,5",
                },  # narrow family -- kept (comprehensive-coverage decision)
                {
                    "id": "B25001",
                    "product": "Detailed Table",
                    "year": "1,5",
                },  # housing -- kept by default (comprehensive-coverage decision)
                {
                    "id": "S0101",
                    "product": "Subject Tables for Specific Topics",
                    "year": "1,5",
                },  # wrong product -- dropped
                {"id": "B19013", "product": "Detailed Table", "year": "1,5"},
                {
                    "id": "B25142",
                    "product": "Detailed Table",
                    "year": "1",
                },  # 1-year only -- dropped (never published at 5-year)
                {
                    "id": "B21007",
                    "product": "Detailed Table",
                    "year": "",
                },  # blank year (pre-fix manifest) -- kept, unknown != excluded
            ]
        }
        with TemporaryDirectory() as directory:
            # relevant_acs_tables reads data_root().parent / "meta" / ...,
            # matching every other ACS metadata path in this module.
            manifest_dir = Path(directory) / "meta" / "acs" / "2099"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "tables.json").write_text(json.dumps(manifest))
            with patch(
                "opendiscourse_research.ingestion.census.data_root",
                return_value=Path(directory) / "raw",
            ):
                self.assertEqual(
                    relevant_acs_tables(2099),
                    [
                        "B01001",
                        "B01001A",
                        "B13002",
                        "B19013",
                        "B21007",
                        "B25001",
                    ],
                )
                self.assertEqual(
                    relevant_acs_tables(2099, include_housing_detail=False),
                    ["B01001", "B01001A", "B13002", "B19013", "B21007"],
                )
                self.assertEqual(
                    relevant_acs_tables(2099, include_housing_detail=True),
                    [
                        "B01001",
                        "B01001A",
                        "B13002",
                        "B19013",
                        "B21007",
                        "B25001",
                    ],
                )

    def test_tiger_zcta_layer_switches_directory_and_suffix_at_the_2020_cutover(
        self,
    ) -> None:
        # Confirmed live: ZCTA5/..._zcta510.zip (2010-vintage boundaries) 404s
        # from TIGER2021 on; ZCTA520/..._zcta520.zip (2020-vintage) 404s before
        # TIGER2020. A single hardcoded directory silently 404s outside its range.
        self.assertIn("ZCTA5/tl_2019_us_zcta510.zip", tiger_layers(2019))
        self.assertIn("ZCTA520/tl_2020_us_zcta520.zip", tiger_layers(2020))
        self.assertIn("ZCTA520/tl_2023_us_zcta520.zip", tiger_layers(2023))

    def test_tiger_artifact_kind_is_vintage_suffixed_not_directory_derived(
        self,
    ) -> None:
        # tiger_load.py's LAYER_INFO is keyed by the vintage-suffixed kind
        # (zcta510/zcta520), not the ZCTA5/ZCTA520 directory name -- deriving
        # `kind` from the directory would silently produce "zcta5" for
        # pre-2020 vintages, an unrecognized layer that _scope() would reject.
        plan = build_tiger_bulk_plan(
            "test",
            [
                resource(
                    "census.tiger",
                    "national:2019:core-boundaries",
                    "National core boundary layers",
                )
            ],
        )
        kinds = {artifact["kind"] for artifact in plan["artifacts"]}
        self.assertIn("zcta510", kinds)
        self.assertNotIn("zcta5", kinds)

    def test_tiger_2022_plan_omits_the_unpublished_cbsa_layer(self) -> None:
        # Confirmed live: Census never published a national CBSA
        # delineation file under TIGER2022 -- every filename tried 404s.
        plan = build_tiger_bulk_plan(
            "test",
            [
                resource(
                    "census.tiger",
                    "national:2022:core-boundaries",
                    "National core boundary layers",
                )
            ],
        )
        kinds = {artifact["kind"] for artifact in plan["artifacts"]}
        self.assertNotIn("cbsa", kinds)
        self.assertEqual(len(plan["artifacts"]), 3)

    def test_tiger_plan_uses_the_requested_vintage_not_2020(self) -> None:
        selected = [
            resource(
                "census.tiger",
                "national:2023:core-boundaries",
                "National core boundary layers",
            )
        ]
        plan = build_tiger_bulk_plan("test", selected)
        self.assertEqual(plan["selection"]["boundary_vintage"], 2023)
        self.assertTrue(
            all("TIGER2023" in artifact["url"] for artifact in plan["artifacts"])
        )


class TestBulkLifecycle(unittest.TestCase):
    def test_approval_requires_successful_preview_and_records_explicit_scope(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "plan.yaml"
            path.write_text(
                yaml.safe_dump(
                    {
                        "state": "draft",
                        "artifacts": [{"artifact_key": "x"}],
                        "storage": {},
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "No preflight"):
                approve_plan(path, {"geography_levels": ["county"]})
            path.with_suffix(".preview.json").write_text(json.dumps({"approved": True}))
            result = approve_plan(path, {"geography_levels": ["county"]})
            self.assertEqual(result["state"], "approved")
            self.assertEqual(
                result["canonical_load_scope"], {"geography_levels": ["county"]}
            )
            self.assertEqual(result["storage"]["state"], "previewed")

    def test_lifecycle_transition_cannot_skip_or_repeat_a_phase(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "plan.yaml"
            path.write_text(yaml.safe_dump({"state": "downloaded"}))
            with self.assertRaisesRegex(ValueError, "must be 'staged'"):
                advance_plan(path, "staged", "loaded", "load", {})
            result = advance_plan(
                path, "downloaded", "staged", "staging", {"row_count": 2}
            )
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

    def test_acs_table_partitions_are_disjoint_and_cover_every_table(self) -> None:
        plan = {
            "artifacts": [
                {"kind": "detailed_table", "table_id": table_id}
                for table_id in ("B01001", "B02001", "B08128", "B19013", "B25001")
            ]
        }
        partitions = _table_id_partitions(plan, workers=3)
        self.assertEqual(len(partitions), 3)
        covered = set().union(*partitions)
        self.assertEqual(covered, {"B01001", "B02001", "B08128", "B19013", "B25001"})
        for left in partitions:
            for right in partitions:
                if left is not right:
                    self.assertFalse(left & right)

    def test_acs_table_partitions_never_exceed_the_table_count(self) -> None:
        plan = {
            "artifacts": [
                {"kind": "detailed_table", "table_id": table_id}
                for table_id in ("B01001", "B02001")
            ]
        }
        partitions = _table_id_partitions(plan, workers=8)
        self.assertEqual(len(partitions), 2)

    def test_acs_numeric_cells_preserve_values_and_null_unavailable_markers(
        self,
    ) -> None:
        self.assertEqual(acs_numeric("123.45"), __import__("decimal").Decimal("123.45"))
        for value in (None, "", "N", ".", "-666666666", "-999999999"):
            self.assertIsNone(acs_numeric(value))
        with self.assertRaisesRegex(ValueError, "Invalid ACS numeric"):
            acs_numeric("not-a-number")

    def test_dhc_matrix_preserves_column_offsets_for_skipped_tables(self) -> None:
        import openpyxl

        with TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.xlsx"
            book = openpyxl.Workbook()
            sheet = book.active
            sheet.title = "DHC Table Matrix"
            sheet.append(["title"] * 4)
            sheet.append(["headers"] * 4)
            sheet.append([None, "P1", "P0010001", 5])
            sheet.append([None, "P1", "P0010002", 5])
            sheet.append([None, "H1", "H0010001", 5])
            book.save(path)
            self.assertEqual(_matrix(path, {"H1"}), {5: [("H1", "H0010001", 7)]})
