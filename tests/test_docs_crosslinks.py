"""Regression checks that newcomer-facing docs exist and cross-link correctly."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestDocsCrossLinks(unittest.TestCase):
    def test_getting_started_exists_and_links_to_reference_docs(self) -> None:
        text = (REPO_ROOT / "docs" / "getting-started.md").read_text()
        self.assertIn("README.md", text)
        self.assertIn("AGENTS.md", text)
        self.assertIn("CONTRIBUTING.md", text)

    def test_contributing_exists_and_links_to_getting_started(self) -> None:
        text = (REPO_ROOT / "CONTRIBUTING.md").read_text()
        self.assertIn("docs/getting-started.md", text)
        self.assertIn("AGENTS.md", text)
