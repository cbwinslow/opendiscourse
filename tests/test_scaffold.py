"""Tests for the new-provider scaffold generator."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from opendiscourse_research.scaffold import ScaffoldError, new_provider


def _make_fake_repo(root: Path) -> None:
    (root / "src" / "opendiscourse_research" / "providers").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "inventory").mkdir(parents=True)
    (root / "inventory" / "sources.yaml").write_text(
        "version: 1\nproviders:\n  - id: fred\n    name: FRED\n"
    )


class TestNewProvider(unittest.TestCase):
    def test_rejects_non_snake_case_name(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_fake_repo(root)
            with self.assertRaisesRegex(ScaffoldError, "lowercase snake_case"):
                new_provider("FEC-Bulk", root)

    def test_rejects_existing_provider_module(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_fake_repo(root)
            (root / "src" / "opendiscourse_research" / "providers" / "fec.py").write_text(
                "# already here\n"
            )
            with self.assertRaisesRegex(ScaffoldError, "already exists"):
                new_provider("fec", root)

    def test_rejects_existing_sources_yaml_id(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_fake_repo(root)
            with self.assertRaisesRegex(ScaffoldError, "already has an entry"):
                new_provider("fred", root)

    def test_creates_provider_test_and_sources_yaml_stub(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_fake_repo(root)
            created = new_provider("fec_bulk", root)

            provider_text = created["provider"].read_text()
            self.assertIn("from ..config import settings", provider_text)
            self.assertIn("from ..ingestion.base import client, json_response", provider_text)
            self.assertIn("def sync()", provider_text)
            self.assertIn("NotImplementedError", provider_text)
            self.assertIn("docs/adding-a-provider.md", provider_text)

            test_text = created["test"].read_text()
            self.assertIn("class TestFecBulkProvider(unittest.TestCase)", test_text)
            self.assertIn("self.skipTest(", test_text)

            sources_text = created["sources_yaml"].read_text()
            self.assertIn("id: fec_bulk", sources_text)
            marker = "# --- scaffold:"
            marker_index = sources_text.index(marker)
            appended = sources_text[marker_index:]
            self.assertTrue(
                all(
                    line.strip().startswith("#") or not line.strip()
                    for line in appended.splitlines()
                ),
                "appended block must stay commented out until filled in",
            )
            # Original content must still be intact and still parse.
            parsed = yaml.safe_load(sources_text[:marker_index])
            self.assertEqual(parsed["providers"][0]["id"], "fred")


if __name__ == "__main__":
    unittest.main()
