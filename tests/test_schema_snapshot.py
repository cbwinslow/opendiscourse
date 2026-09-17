"""Guards for the checked-in live schema snapshot used in external reviews."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "docs" / "schema-snapshot"


def _load_export_module():
    spec = importlib.util.spec_from_file_location(
        "export_schema_snapshot",
        REPO_ROOT / "scripts" / "export_schema_snapshot.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSchemaSnapshot(unittest.TestCase):
    def test_redact_dump_strips_user_mapping_passwords(self) -> None:
        module = _load_export_module()
        raw = (
            "CREATE USER MAPPING FOR cbwinslow SERVER openstates_local OPTIONS (\n"
            "    password 'super-secret',\n"
            "    \"user\" 'openstates_fdw'\n"
            ");\n"
        )
        redacted = module.redact_dump(raw)
        self.assertNotIn("super-secret", redacted)
        self.assertIn("password 'REDACTED'", redacted)

    def test_snapshot_files_exist_and_cover_owned_schemas(self) -> None:
        for name in (
            "README.md",
            "opendiscourse.schema.sql",
            "openstates-opencivicdata.schema.sql",
            "catalog.md",
            "openstates-inventory.md",
            "related-files.md",
            "spec-8-1-post-division-membership.md",
            "epic-8-context.md",
            "metadata.json",
        ):
            path = SNAPSHOT / name
            self.assertTrue(path.is_file(), f"missing {path}")
            self.assertGreater(path.stat().st_size, 0, f"empty {path}")

        sql = (SNAPSHOT / "opendiscourse.schema.sql").read_text()
        for schema in ("catalog", "core", "fact", "ingest", "stage", "mart", "leg"):
            self.assertIn(f"CREATE SCHEMA {schema};", sql)
        self.assertIn("CREATE TABLE core.bill", sql)
        self.assertIn(
            "CREATE FOREIGN TABLE openstates_source.opencivicdata_person", sql
        )
        self.assertNotRegex(sql, r"(?i)password\s+'(?!REDACTED')")

        catalog = (SNAPSHOT / "catalog.md").read_text()
        self.assertIn("`membership`", catalog)
        self.assertIn("#### `core.membership`", catalog)
        self.assertIn("openstates_source", catalog)

        ocd = (SNAPSHOT / "openstates-opencivicdata.schema.sql").read_text()
        self.assertIn("CREATE TABLE public.opencivicdata_post", ocd)
        self.assertIn("CREATE TABLE public.opencivicdata_membership", ocd)

        related = (SNAPSHOT / "related-files.md").read_text()
        self.assertIn("migrations/versions/", related)
        self.assertIn("sql/query/", related)
        self.assertIn("inventory/sources.yaml", related)
        self.assertIn("scripts/export_schema_snapshot.py", related)
        self.assertIn("SPEC.md", related)

        meta = json.loads((SNAPSHOT / "metadata.json").read_text())
        self.assertEqual(meta["database"], "opendiscourse")
        self.assertIn("alembic_versions", meta)
