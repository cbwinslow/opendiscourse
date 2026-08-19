"""Tests for portable default configuration."""

from __future__ import annotations

import unittest

from opendiscourse_research.config import Settings


class TestSettingsDefaults(unittest.TestCase):
    def test_data_root_default_is_project_relative_not_maintainer_specific(
        self,
    ) -> None:
        default = Settings.model_fields["data_root"].default
        self.assertFalse(default.startswith("/home/"))
        self.assertEqual(default, "./data-lake/opendiscourse/raw")
