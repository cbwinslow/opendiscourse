"""Tests for pure Census bulk health classification rules."""
from __future__ import annotations

import unittest

from opendiscourse_research.censushealth import classify_plan


class TestCensusHealth(unittest.TestCase):
    def test_loaded_non_acs_plan_requires_artifacts_and_canonical_rows(self) -> None:
        plan = {"dataset": "census.population_estimates", "state": "loaded", "artifacts": [{"artifact_key": "pep"}]}
        self.assertEqual(classify_plan(plan, [{"artifact_key": "pep", "status": "downloaded"}], 3)[0], "healthy")
        self.assertEqual(classify_plan(plan, [{"artifact_key": "pep", "status": "downloaded"}], 0)[0], "failed")
        self.assertEqual(classify_plan(plan, [], 3), ("failed", ["missing artifact: pep"]))

    def test_preload_states_require_attention_and_failed_artifact_is_failure(self) -> None:
        plan = {"dataset": "census.tiger", "state": "approved", "artifacts": [{"artifact_key": "tiger"}]}
        self.assertEqual(classify_plan(plan, [{"artifact_key": "tiger", "status": "planned"}], 0)[0], "attention")
        plan["state"] = "loaded"
        self.assertEqual(classify_plan(plan, [{"artifact_key": "tiger", "status": "failed"}], 1)[0], "failed")

    def test_loaded_acs_plan_requires_artifact_linked_canonical_rows(self) -> None:
        plan = {"dataset": "census.acs_5_bulk", "state": "loaded", "artifacts": [{"artifact_key": "acs"}]}
        self.assertEqual(classify_plan(plan, [{"artifact_key": "acs", "status": "downloaded"}], 2)[0], "healthy")
        self.assertEqual(classify_plan(plan, [{"artifact_key": "acs", "status": "downloaded"}], 0)[0], "failed")
