"""Unit tests for legislative persistence repository and parser seam."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from opendiscourse_research.ingestion.base import IngestionRun
from opendiscourse_research.repositories.legislation import (
    ensure_us_legislative_session,
    loaded_artifact_members,
    parse_billstatus_xml,
    resolve_bill_sponsorship_people,
    save_billstatus_bill,
    sync_openstates_federal_people,
)

SAMPLE_XML = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<billStatus>
  <version>3.0.0</version>
  <bill>
    <number>184</number>
    <updateDate>2024-07-24T15:24:11Z</updateDate>
    <type>HR</type>
    <introducedDate>2023-01-09</introducedDate>
    <congress>118</congress>
    <title>To promote accountability and transparency in future executive orders.</title>
    <committees>
      <item>
        <systemCode>hsii00</systemCode>
        <name>Natural Resources Committee</name>
        <chamber>House</chamber>
        <type>Standing</type>
      </item>
    </committees>
    <actions>
      <item>
        <actionDate>2023-01-09</actionDate>
        <text>Referred to the House Committee on Natural Resources.</text>
        <type>IntroReferral</type>
        <actionCode>H11100</actionCode>
      </item>
    </actions>
    <sponsors>
      <item>
        <bioguideId>M000871</bioguideId>
        <fullName>Rep. Mann, Tracey [R-KS-1]</fullName>
        <party>R</party>
        <state>KS</state>
        <district>1</district>
      </item>
    </sponsors>
    <cosponsors>
      <item>
        <bioguideId>D000615</bioguideId>
        <fullName>Rep. Duncan, Jeff [R-SC-3]</fullName>
        <sponsorshipDate>2023-01-10</sponsorshipDate>
        <isOriginalCosponsor>N</isOriginalCosponsor>
      </item>
    </cosponsors>
    <policyArea>
      <name>Environmental Protection</name>
    </policyArea>
    <subjects>
      <legislativeSubjects>
        <item>
          <name>Congressional oversight</name>
        </item>
      </legislativeSubjects>
    </subjects>
    <textVersions>
      <item>
        <type>Introduced in House</type>
        <date>2023-01-09T05:00:00Z</date>
        <formats>
          <item>
            <url>https://www.govinfo.gov/content/pkg/BILLS-118hr184ih/xml/BILLS-118hr184ih.xml</url>
          </item>
        </formats>
      </item>
    </textVersions>
    <latestAction>
      <actionDate>2023-01-09</actionDate>
      <text>Referred to the House Committee on Natural Resources.</text>
    </latestAction>
  </bill>
</billStatus>
"""


class TestLegislationPersistence(unittest.TestCase):
    def test_parse_billstatus_xml(self) -> None:
        parsed = parse_billstatus_xml(SAMPLE_XML, member_name="BILLSTATUS-118hr184.xml")
        self.assertEqual(parsed["congress"], 118)
        self.assertEqual(parsed["bill_type"], "hr")
        self.assertEqual(parsed["bill_number"], "184")
        self.assertEqual(
            parsed["title"],
            "To promote accountability and transparency in future executive orders.",
        )
        self.assertEqual(parsed["introduced_date"], "2023-01-09")
        self.assertEqual(len(parsed["sponsorships"]), 2)
        self.assertEqual(parsed["sponsorships"][0]["role"], "sponsor")
        self.assertEqual(parsed["sponsorships"][0]["member_external_id"], "M000871")
        self.assertEqual(parsed["sponsorships"][1]["role"], "cosponsor")
        self.assertEqual(parsed["sponsorships"][1]["member_external_id"], "D000615")

        self.assertEqual(len(parsed["actions"]), 1)
        self.assertEqual(parsed["actions"][0]["source_ordinal"], 1)
        self.assertEqual(parsed["actions"][0]["action_date"], "2023-01-09")

        self.assertEqual(len(parsed["committees"]), 1)
        self.assertEqual(parsed["committees"][0]["external_id"], "hsii00")

        self.assertEqual(len(parsed["subjects"]), 2)
        labels = [s["label"] for s in parsed["subjects"]]
        self.assertIn("Environmental Protection", labels)
        self.assertIn("Congressional oversight", labels)

        self.assertEqual(len(parsed["documents"]), 1)
        self.assertEqual(
            parsed["documents"][0]["source_url"],
            "https://www.govinfo.gov/content/pkg/BILLS-118hr184ih/xml/BILLS-118hr184ih.xml",
        )

    def test_save_billstatus_bill_lineage_validation(self) -> None:
        parsed = parse_billstatus_xml(SAMPLE_XML)
        with self.assertRaises(ValueError):
            save_billstatus_bill(parsed, legislative_session_id="dummy-session-id")

    def test_parse_blank_document_date_as_none(self) -> None:
        parsed = parse_billstatus_xml(SAMPLE_XML.replace("2023-01-09T05:00:00Z", ""))
        self.assertIsNone(parsed["documents"][0]["published_at"])

    def test_ensure_us_legislative_session_lineage_validation(self) -> None:
        with self.assertRaises(ValueError):
            ensure_us_legislative_session(118)

    def test_save_billstatus_bill_mock_persistence(self) -> None:
        parsed = parse_billstatus_xml(SAMPLE_XML, member_name="BILLSTATUS-118hr184.xml")
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        # Mock returning bill_id
        mock_cur.fetchone.side_effect = [
            {"bill_id": "11111111-1111-1111-1111-111111111111"},  # upsert_bill
            {
                "person_id": "22222222-2222-2222-2222-222222222222"
            },  # find_person sponsor
            {"person_id": None},  # find_person cosponsor
            {"document_id": "33333333-3333-3333-3333-333333333333"},  # upsert_document
        ]

        bill_id = save_billstatus_bill(
            parsed,
            legislative_session_id="00000000-0000-0000-0000-000000000000",
            source_artifact_id="aaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            source_member="BILLSTATUS-118hr184.xml",
            conn=mock_conn,
        )

        self.assertEqual(bill_id, "11111111-1111-1111-1111-111111111111")
        self.assertTrue(mock_cur.execute.called)

    def test_loaded_artifact_members_uses_identifier_lineage(self) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {"source_member": "BILLSTATUS-118hr1.xml"},
            {"source_member": "BILLSTATUS-118hr2.xml"},
        ]

        result = loaded_artifact_members(
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", conn=mock_conn
        )

        self.assertEqual(result, {"BILLSTATUS-118hr1.xml", "BILLSTATUS-118hr2.xml"})
        query, params = mock_cur.execute.call_args.args
        self.assertIn("govinfo.package", query)
        self.assertEqual(params["artifact_id"], "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    def test_ingestion_run_can_record_partial_completion(self) -> None:
        mock_session = MagicMock()
        active_session = mock_session.return_value.__enter__.return_value
        active_session.execute.return_value.scalar_one.return_value = (
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        )

        with (
            patch("opendiscourse_research.ingestion.base.session", mock_session),
            IngestionRun(
                "congress.govinfo_billstatus", {"congress": 119}, mode="backfill"
            ) as run,
        ):
            run.record_count = 7
            run.mark_partial()

        self.assertEqual(active_session.execute.call_count, 2)
        self.assertFalse(hasattr(IngestionRun, "conn"))

    def test_ingestion_run_records_failure_through_mapped_session(self) -> None:
        mock_session = MagicMock()
        active_session = mock_session.return_value.__enter__.return_value
        active_session.execute.return_value.scalar_one.return_value = (
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        )

        with (
            patch("opendiscourse_research.ingestion.base.session", mock_session),
            self.assertRaisesRegex(RuntimeError, "expected"),
            IngestionRun("openstates.legislation", {"test": True}),
        ):
            raise RuntimeError("expected")

        self.assertEqual(active_session.execute.call_count, 2)

    def test_openstates_people_sync_preserves_identifier_conflicts(self) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.side_effect = [
            [
                {
                    "ocd_id": "ocd-person/example",
                    "name": "Example Person",
                    "given_name": "Example",
                    "family_name": "Person",
                    "extras": {},
                }
            ],
            [{"namespace": "bioguide", "external_id": "E000001"}],
        ]
        mock_cur.fetchone.side_effect = [
            {"person_id": "11111111-1111-1111-1111-111111111111"},
            None,
        ]

        result = sync_openstates_federal_people(mock_conn)

        self.assertEqual(
            result, {"people": 1, "identifiers": 0, "identifier_conflicts": 1}
        )

    def test_resolve_bill_sponsorship_people_returns_updated_count(self) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            {"bill_sponsorship_id": "a"},
            {"bill_sponsorship_id": "b"},
        ]

        self.assertEqual(resolve_bill_sponsorship_people(mock_conn), 2)
        self.assertIn(
            "UPDATE core.bill_sponsorship", mock_cur.execute.call_args.args[0]
        )


if __name__ == "__main__":
    unittest.main()
