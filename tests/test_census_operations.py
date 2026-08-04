"""Tests for the metadata-only Census refresh contract."""
from __future__ import annotations

import unittest
from pathlib import Path

from opendiscourse_research.plans import HANDLERS, load_plans, validate_plans


class TestCensusOperations(unittest.TestCase):
    def test_census_metadata_plan_is_explicit_and_non_bulk(self) -> None:
        plan = next(item for item in load_plans() if item["id"] == "censusmeta")
        self.assertEqual(plan["handler"], "census_metadata")
        self.assertEqual(plan["cadence"], "weekly")
        self.assertEqual(plan["parameters"], {})
        self.assertIn("never downloads", plan["notes"])

    def test_census_metadata_handler_is_validated(self) -> None:
        self.assertIn("census_metadata", HANDLERS)
        self.assertEqual(validate_plans(), [])

    def test_systemd_units_keep_refresh_and_health_read_only(self) -> None:
        root = Path(__file__).resolve().parents[1] / "ops" / "systemd"
        metadata = (root / "opendiscourse-census-metadata.service").read_text()
        health = (root / "opendiscourse-census-health.service").read_text()
        self.assertIn("plan-run censusmeta", metadata)
        self.assertIn("census-health", health)
        self.assertNotIn("bulk-download", metadata + health)
