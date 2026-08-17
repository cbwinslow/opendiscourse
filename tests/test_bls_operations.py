"""Tests for the curated BLS plan and manifest contract."""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from opendiscourse_research.plans import HANDLERS, load_plans, validate_plans


class TestBLSOperations(unittest.TestCase):
    def test_bls_core_plan_is_curated_and_valid(self) -> None:
        plan = next(item for item in load_plans() if item["id"] == "blscore")
        self.assertEqual(plan["handler"], "bls_core")
        self.assertEqual(plan["cadence"], "weekly")
        self.assertEqual(plan["parameters"], {"max_priority": 1})
        self.assertIn("never attempt all", plan["notes"])

    def test_bls_core_handler_is_validated(self) -> None:
        self.assertIn("bls_core", HANDLERS)
        self.assertEqual(validate_plans(), [])

    def test_bls_manifest_entries_are_well_formed(self) -> None:
        path = (
            Path(__file__).resolve().parents[1]
            / "inventory"
            / "core_bls_series.yaml"
        )
        series = yaml.safe_load(path.read_text())["series"]
        self.assertTrue(series)
        for entry in series:
            self.assertIn(entry["dataset"], {"bls.cpi", "bls.laus"})
            self.assertIn(entry["priority"], (1, 2, 3))
            self.assertTrue(entry["series_id"])
            self.assertTrue(entry["label"])
