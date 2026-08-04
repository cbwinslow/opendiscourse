"""Tests for the read-only OpenStates congressional vote refresh plan."""

from __future__ import annotations

import unittest
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import yaml

from opendiscourse_research.openstatesrefresh import (
    build_openstates_vote_dry_run,
    require_openstates_snapshot_download_approval,
    validate_openstates_vote_contract,
)
from opendiscourse_research.openstatessnapshot import validate_snapshot_artifact
from opendiscourse_research.peopleload import load_openstates_votes


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

    def test_snapshot_validator_requires_checksum_and_vote_tables(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "snapshot.pgdump"
            artifact.write_bytes(b"immutable provider snapshot")
            manifest = root / "snapshot.yaml"
            manifest.write_text(
                yaml.safe_dump(
                    {
                        "schema": 1,
                        "provider": "openstates",
                        "dataset": "openstates.dump",
                        "artifact_key": "openstates-public-2026-08",
                        "remote_url": "https://example.test/snapshot.pgdump",
                        "local_path": str(artifact),
                        "period": "2026-08",
                        "bytes": artifact.stat().st_size,
                        "checksum_sha256": sha256(artifact.read_bytes()).hexdigest(),
                        "expected_tables": [
                            "public.opencivicdata_legislativesession",
                            "public.opencivicdata_voteevent",
                            "public.opencivicdata_personvote",
                        ],
                    }
                )
            )
            tables = {
                "public.opencivicdata_legislativesession",
                "public.opencivicdata_voteevent",
                "public.opencivicdata_personvote",
            }
            result = validate_snapshot_artifact(manifest, table_lister=lambda _: tables)
            self.assertTrue(result["read_only"])
            self.assertEqual(result["archive_table_count"], 3)

    def test_snapshot_validator_rejects_missing_archive_table(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "snapshot.pgdump"
            artifact.write_bytes(b"immutable provider snapshot")
            manifest = root / "snapshot.yaml"
            manifest.write_text(
                yaml.safe_dump(
                    {
                        "schema": 1,
                        "provider": "openstates",
                        "dataset": "openstates.dump",
                        "artifact_key": "openstates-public-2026-08-missing",
                        "remote_url": "https://example.test/snapshot.pgdump",
                        "local_path": str(artifact),
                        "period": "2026-08",
                        "bytes": artifact.stat().st_size,
                        "checksum_sha256": sha256(artifact.read_bytes()).hexdigest(),
                        "expected_tables": [
                            "public.opencivicdata_legislativesession",
                            "public.opencivicdata_voteevent",
                            "public.opencivicdata_personvote",
                        ],
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "missing required tables"):
                validate_snapshot_artifact(
                    manifest,
                    table_lister=lambda _: {"public.opencivicdata_voteevent"},
                )

    def test_vote_loader_resumes_from_committed_checkpoint(self) -> None:
        run = MagicMock()
        run.conn = MagicMock()
        run.run_id = "run-119"
        run.__enter__.return_value = run
        with (
            patch("opendiscourse_research.peopleload.IngestionRun", return_value=run),
            patch(
                "opendiscourse_research.peopleload.register_artifact",
                return_value={"artifact_id": "artifact-119"},
            ),
            patch(
                "opendiscourse_research.peopleload.get_resume_cursor",
                return_value={"cursor": {"last_ocd_id": "ocd-vote-10"}},
            ),
            patch(
                "opendiscourse_research.peopleload.persist_openstates_votes",
                side_effect=[
                    {
                        "roll_calls": 1,
                        "member_votes": 2,
                        "unresolved_people": 0,
                        "last_ocd_id": "ocd-vote-11",
                    },
                    {
                        "roll_calls": 0,
                        "member_votes": 0,
                        "unresolved_people": 0,
                        "last_ocd_id": "ocd-vote-11",
                    },
                ],
            ) as page_loader,
            patch("opendiscourse_research.peopleload.save_resume_cursor") as save_cursor,
        ):
            result = load_openstates_votes(119, limit=2, page_size=1, resume=True)
        self.assertEqual(page_loader.call_args_list[0].args[-1], "ocd-vote-10")
        self.assertEqual(result["resumed_from"], "ocd-vote-10")
        self.assertEqual(result["next_cursor"], "ocd-vote-11")
        self.assertEqual(result["checkpoint_state"], "complete")
        self.assertEqual(save_cursor.call_args_list[-1].args[-2], "complete")
