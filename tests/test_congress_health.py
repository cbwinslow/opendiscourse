"""Coverage-evidence tests for congressional health reporting."""

from __future__ import annotations

import unittest

from opendiscourse_research.congresshealth import billstatus_coverage


class TestCongressHealth(unittest.TestCase):
    def test_billstatus_is_complete_only_with_all_promotion_evidence(self) -> None:
        validation = {"official_comparison": [{"congress": 119, "archive_matches_official": True}]}
        reconciliation = {"congress": 119, "summary": {"canonical_bill_missing": 0}, "malformed": []}
        runs = [{"dataset_id": "congress.govinfo_billstatus", "status": "succeeded", "parameters": {"congress": 119, "coverage": "complete"}}]
        self.assertEqual(billstatus_coverage(validation, reconciliation, runs), "complete")

    def test_billstatus_remains_partial_without_complete_archive_validation(self) -> None:
        validation = {"official_comparison": [{"congress": 119, "archive_matches_official": False}]}
        reconciliation = {"congress": 119, "summary": {"canonical_bill_missing": 0}, "malformed": []}
        runs = [{"dataset_id": "congress.govinfo_billstatus", "status": "succeeded", "parameters": {"congress": 119, "coverage": "complete"}}]
        self.assertEqual(billstatus_coverage(validation, reconciliation, runs), "partial")
