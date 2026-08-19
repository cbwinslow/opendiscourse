"""Regression tests for FEC bulk file discovery and row parsing."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from opendiscourse_research.ingestion.fec_bulk import (
    FIELDS,
    discover_family,
    parse_row,
)


class TestFecBulkSchemas(unittest.TestCase):
    def test_indiv_and_oth_share_the_21_column_layout(self) -> None:
        self.assertEqual(FIELDS["indiv"], FIELDS["oth"])
        self.assertEqual(len(FIELDS["indiv"]), 21)
        self.assertEqual(FIELDS["indiv"][0], "cmte_id")
        self.assertEqual(FIELDS["indiv"][-1], "sub_id")

    def test_pas2_adds_cand_id_between_other_id_and_tran_id(self) -> None:
        self.assertEqual(len(FIELDS["pas2"]), 22)
        self.assertIn("cand_id", FIELDS["pas2"])
        self.assertNotIn("cand_id", FIELDS["indiv"])

    def test_oppexp_has_25_named_columns(self) -> None:
        self.assertEqual(len(FIELDS["oppexp"]), 25)
        self.assertEqual(FIELDS["oppexp"][-1], "back_ref_tran_id")

    def test_parse_row_maps_a_real_indiv_sample_correctly(self) -> None:
        line = (
            "C00878454|N|12P|P2024|202408299675313804|15E|IND|JENNINGS, EMILY|"
            "SOMERVILLE|MA|021432389|SKADDEN ARPS|ATTORNEY|08052024|250|"
            "C00401224|4187316|1813451||* EARMARKED CONTRIBUTION: SEE BELOW|"
            "4083020242017155126"
        )
        parsed = parse_row("indiv", line.split("|"))
        self.assertEqual(parsed["cmte_id"], "C00878454")
        self.assertEqual(parsed["name"], "JENNINGS, EMILY")
        self.assertEqual(parsed["transaction_amt"], "250")
        self.assertEqual(parsed["sub_id"], "4083020242017155126")

    def test_parse_row_tolerates_oppexps_trailing_delimiter_artifact(self) -> None:
        # oppexp.txt rows end with a trailing "|", producing one extra empty
        # field beyond the 25 named columns -- a real publisher quirk, not a
        # schema the FEC actually documents as 26 columns.
        fields = ["x"] * 25 + [""]
        parsed = parse_row("oppexp", fields)
        self.assertEqual(len(parsed), 25)
        self.assertEqual(parsed["back_ref_tran_id"], "x")

    def test_parse_row_rejects_a_field_count_that_matches_no_known_layout(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected 21"):
            parse_row("indiv", ["only", "three", "fields"])

    def test_parse_row_rejects_unknown_family(self) -> None:
        with self.assertRaises(KeyError):
            parse_row("not-a-family", ["a"])


class TestFecBulkDiscovery(unittest.TestCase):
    def test_discover_family_finds_only_that_familys_cycle_archives(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("pas200.zip", "pas224.zip", "indiv24.zip", "pas2_notes.txt"):
                (root / name).write_bytes(b"x" * 10)
            found = discover_family("pas2", root)
            self.assertEqual([entry["cycle"] for entry in found], [2000, 2024])
            self.assertEqual(
                found[-1]["url"],
                "https://www.fec.gov/files/bulk-downloads/2024/pas224.zip",
            )
            self.assertEqual(found[0]["bytes"], 10)

    def test_discover_family_rejects_unknown_family(self) -> None:
        with (
            TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "Unknown FEC bulk family"),
        ):
            discover_family("bogus", Path(directory))

    def test_discover_family_returns_empty_for_a_missing_root(self) -> None:
        self.assertEqual(discover_family("pas2", Path("/no/such/directory")), [])


if __name__ == "__main__":
    unittest.main()
