"""Tests for resumable GovInfo BILLSTATUS archive repair helpers."""

from __future__ import annotations

import unittest

from opendiscourse_research.govbackfill import pending_archive_files


class TestGovInfoBackfill(unittest.TestCase):
    def test_pending_archive_files_selects_only_missing_xml_members(self) -> None:
        listing = {
            "files": [
                {"name": "BILLSTATUS-119hr1.xml", "link": "https://example.test/1"},
                {"name": "BILLSTATUS-119hr2.xml", "link": "https://example.test/2"},
                {"name": "README.txt", "link": "https://example.test/readme"},
            ]
        }
        result = pending_archive_files(listing, {"BILLSTATUS-119hr1.xml"})
        self.assertEqual(result, [listing["files"][1]])

    def test_pending_archive_files_requires_a_download_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "no download URL"):
            pending_archive_files({"files": [{"name": "BILLSTATUS-119hr1.xml"}]}, set())
