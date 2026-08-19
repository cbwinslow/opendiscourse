"""Coverage-evidence tests for congressional health reporting."""

from __future__ import annotations

import unittest

from opendiscourse_research.congresshealth import (
    billstatus_coverage,
    has_identity_attention,
    is_recovered_run,
)


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

    def test_recovered_run_is_not_an_active_failure(self) -> None:
        self.assertTrue(
            is_recovered_run(
                {"error_message": "Recovered by congressional health check: stale run."}
            )
        )
        self.assertFalse(is_recovered_run({"error_message": "connection refused"}))

    def test_unresolved_voters_require_health_attention(self) -> None:
        self.assertTrue(has_identity_attention({"unresolved_voters": 1}))
        self.assertFalse(
            has_identity_attention(
                {"unresolved_voters": 0, "unresolved_sponsorships": 0}
            )
        )
