"""Opt-in database smoke tests for Census bulk stage/load idempotence.

Run only against a disposable database:
``OPENDISCOURSE_TEST_DATABASE_URL=... uv run --extra ingest python -m unittest tests.test_census_bulk_integration``.
"""
from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from opendiscourse_research.config import settings
from opendiscourse_research.db import apply_migrations, connect
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion.cbp_load import load_cbp, stage_cbp
from opendiscourse_research.ingestion.pep_load import load_pep, stage_pep


TEST_DATABASE_URL = __import__("os").environ.get("OPENDISCOURSE_TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "Set OPENDISCOURSE_TEST_DATABASE_URL to run database integration tests")
class TestCensusBulkDatabaseIntegration(unittest.TestCase):
    """Use generated source artifacts only; never call Census during tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._original_url = settings.database_url
        settings.database_url = str(TEST_DATABASE_URL)
        apply_migrations()

    @classmethod
    def tearDownClass(cls) -> None:
        settings.database_url = cls._original_url

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _register(self, key: str, path: Path) -> None:
        register_local(ArtifactSpec("census.integration", key, "https://example.test/" + path.name, path.name), path)

    def _remove_artifact(self, key: str) -> None:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s", (key,))
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM fact.business_pattern WHERE source_artifact_id=%s", (row["artifact_id"],))
                cur.execute("DELETE FROM fact.population_estimate WHERE source_artifact_id=%s", (row["artifact_id"],))
                cur.execute("DELETE FROM stage.cbp_row WHERE artifact_id=%s", (row["artifact_id"],))
                cur.execute("DELETE FROM stage.pep_row WHERE artifact_id=%s", (row["artifact_id"],))
                cur.execute("DELETE FROM ingest.artifact WHERE artifact_id=%s", (row["artifact_id"],))
            cur.execute("DELETE FROM core.geography WHERE geography_type='state' AND geoid='99'")
            conn.commit()

    def test_cbp_generated_zip_stages_and_loads_idempotently(self) -> None:
        key = "cbp-2023-cbp23st"
        self._remove_artifact(key)
        path = Path(self.temp.name) / "cbp.zip"
        with ZipFile(path, "w") as archive:
            archive.writestr("cbp23st.txt", "fipstate,naics,lfo,est,emp,qp1,ap,emp_nf,qp1_nf,ap_nf\n99,00,,10,20,30,40,,,,\n")
        self._register(key, path)
        plan = {"state": "downloaded", "selection": {"release_year": 2023}, "canonical_load_scope": {"geography_levels": ["state"]}}
        self.assertEqual(stage_cbp(plan), 1)
        plan["state"] = "staged"
        self.assertEqual(load_cbp(plan), 1)
        load_cbp(plan)
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM fact.business_pattern WHERE source_artifact_id=(SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s)", (key,))
            self.assertEqual(cur.fetchone()["count"], 1)
        self._remove_artifact(key)

    def test_pep_generated_csv_stages_and_loads_all_vintage_years(self) -> None:
        key = "pep-2025-state-totals"
        self._remove_artifact(key)
        path = Path(self.temp.name) / "pep.csv"
        with path.open("w", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=["SUMLEV", "STATE", "NAME", *[f"POPESTIMATE{year}" for year in range(2020, 2026)]])
            writer.writeheader(); writer.writerow({"SUMLEV": "040", "STATE": "99", "NAME": "Integration State", **{f"POPESTIMATE{year}": str(year) for year in range(2020, 2026)}})
        self._register(key, path)
        plan = {"state": "downloaded", "selection": {"vintage": 2025}, "canonical_load_scope": {"geography_levels": ["state"]}}
        self.assertEqual(stage_pep(plan), 1)
        plan["state"] = "staged"
        self.assertEqual(load_pep(plan), 6)
        load_pep(plan)
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM fact.population_estimate WHERE source_artifact_id=(SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s)", (key,))
            self.assertEqual(cur.fetchone()["count"], 6)
        self._remove_artifact(key)
