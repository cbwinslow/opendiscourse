"""Tests for the read-only OpenStates congressional vote refresh plan."""

from __future__ import annotations

import unittest

from opendiscourse_research.openstatesrefresh import (
    build_openstates_vote_dry_run,
    require_openstates_snapshot_download_approval,
    validate_openstates_vote_contract,
)


def contract() -> dict:
    """Return the minimal reviewed snapshot-refresh contract fixture."""
    return {
        "id": "openstatesvotes",
        "provider": "openstates",
        "kind": "snapshot_incremental",
        "enabled": False,
        "approval": "pending",
        "selection": {"congresses": [118, 119], "entities": ["voteevent", "personvote"]},
        "cursor": {"strategy": "ocd_vote_event_keyset", "key": "ocd_id"},
        "provenance": {"source": "openstates_source"},
        "snapshot": {"endpoint_template": "https://example.test/{YYYY-MM}"},
        "storage": {"reserve_gib": 100},
        "validation": {
            "dry_run_required": True,
            "reconcile_command": "reconcile-openstates-votes",
            "idempotency_required": True,
        },
    }


class TestOpenStatesRefreshPlan(unittest.TestCase):
    def test_contract_requires_keyset_cursor_and_snapshot_endpoint(self) -> None:
        candidate = contract()
        validate_openstates_vote_contract(candidate)
        candidate["cursor"]["key"] = "offset"
        with self.assertRaisesRegex(ValueError, "keyset cursor"):
            validate_openstates_vote_contract(candidate)

    def test_unapproved_dry_run_is_explicitly_no_write(self) -> None:
        result = build_openstates_vote_dry_run(
            contract(),
            {"119": {"congress": "119", "source_events": 739}},
            200 * 1024**3,
        )
        self.assertEqual(result["state"], "approval_required")
        self.assertEqual(
            result["no_writes"],
            {
                "provider": True,
                "source_snapshot": True,
                "canonical_tables": True,
                "ingest_run": True,
            },
        )
        self.assertTrue(result["storage"]["sufficient_reserve"])

    def test_data_snapshot_download_requires_specific_approval(self) -> None:
        candidate = contract()
        with self.assertRaisesRegex(ValueError, "disabled by contract"):
            require_openstates_snapshot_download_approval(candidate)
        candidate["enabled"] = True
        with self.assertRaisesRegex(ValueError, "approved_snapshot_acquisition"):
            require_openstates_snapshot_download_approval(candidate)
        candidate["approval"] = "approved_snapshot_acquisition"
        require_openstates_snapshot_download_approval(candidate)
