"""Opt-in database smoke tests for Census bulk stage/load idempotence.

Run only against a disposable database:
``OPENDISCOURSE_TEST_DATABASE_URL=... uv run --extra ingest python -m unittest tests.test_census_bulk_integration``.
"""

from __future__ import annotations

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import apply_migrations, connect
from opendiscourse_research.ingestion.acs_load import load_acs_bulk, stage_acs_bulk
from opendiscourse_research.ingestion.bulk import ArtifactSpec, register_local
from opendiscourse_research.ingestion.cbp_load import load_cbp, stage_cbp
from opendiscourse_research.ingestion.dhc_load import load_dhc, stage_dhc
from opendiscourse_research.ingestion.pep_load import load_pep, stage_pep
from opendiscourse_research.ingestion.tiger_load import load_tiger, stage_tiger

TEST_DATABASE_URL = __import__("os").environ.get("OPENDISCOURSE_TEST_DATABASE_URL")


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "Set OPENDISCOURSE_TEST_DATABASE_URL to run database integration tests",
)
class TestCensusBulkDatabaseIntegration(unittest.TestCase):
    """Use generated source artifacts only; never call Census during tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._original_url = settings.database_url
        settings.database_url = str(TEST_DATABASE_URL)
        apply_migrations()
        sync_inventory()

    @classmethod
    def tearDownClass(cls) -> None:
        settings.database_url = cls._original_url

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _register(self, dataset_id: str, key: str, path: Path) -> None:
        register_local(
            ArtifactSpec(
                dataset_id, key, "https://example.test/" + path.name, path.name
            ),
            path,
        )

    def _remove_artifact(self, key: str) -> None:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s", (key,)
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "DELETE FROM fact.business_pattern WHERE source_artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM fact.acs_bulk_estimate WHERE source_artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM fact.population_estimate WHERE source_artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM fact.decennial_dhc_value WHERE source_artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM core.geography_boundary WHERE source_artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM stage.cbp_row WHERE artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM stage.acs_bulk_row WHERE artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM stage.pep_row WHERE artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM stage.dhc_geo_row WHERE artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM stage.tiger_feature WHERE artifact_id=%s",
                    (row["artifact_id"],),
                )
                cur.execute(
                    "DELETE FROM ingest.artifact WHERE artifact_id=%s",
                    (row["artifact_id"],),
                )
            cur.execute(
                "DELETE FROM core.geography WHERE geography_type='state' AND geoid='99'"
            )
            conn.commit()

    def test_cbp_generated_zip_stages_and_loads_idempotently(self) -> None:
        key = "cbp-2023-cbp23st"
        self._remove_artifact(key)

        path = Path(self.temp.name) / "cbp.zip"
        with ZipFile(path, "w") as archive:
            archive.writestr(
                "cbp23st.txt",
                "fipstate,naics,lfo,est,emp,qp1,ap,emp_nf,qp1_nf,ap_nf\n99,00,,10,20,30,40,,,,\n",
            )
        self._register("census.business_patterns", key, path)
        plan = {
            "state": "downloaded",
            "selection": {"release_year": 2023},
            "canonical_load_scope": {"geography_levels": ["state"]},
        }
        self.assertEqual(stage_cbp(plan), 1)
        plan["state"] = "staged"
        self.assertEqual(load_cbp(plan), 1)
        load_cbp(plan)
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM fact.business_pattern WHERE source_artifact_id=(SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s)",
                (key,),
            )
            self.assertEqual(cur.fetchone()["count"], 1)
        self._remove_artifact(key)

    def test_acs_generated_dat_stages_and_loads_idempotently(self) -> None:
        key = "acs-2024-b25001-integration"
        self._remove_artifact(key)
        path = Path(self.temp.name) / "acs.dat"
        path.write_text(
            "GEO_ID|B25001_E001|B25001_M001|B25001_E002|B25001_M002\n"
            "0500000US99001|100|7|N|.\n"
            "0400000US99|200|9|-999999999|4\n"
            "0100000US|300|11|12|1\n"
        )
        self._register("census.acs_5_bulk", key, path)
        plan = {
            "state": "downloaded",
            "canonical_load_scope": {"geography_types": ["county", "state"]},
            "artifacts": [
                {
                    "artifact_key": key,
                    "kind": "detailed_table",
                    "release_year": 2024,
                    "table_id": "B25001",
                }
            ],
        }
        self.assertEqual(stage_acs_bulk(plan), 2)
        plan["state"] = "staged"
        self.assertEqual(load_acs_bulk(plan), 8)
        self.assertEqual(load_acs_bulk(plan), 8)
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT geography.geoid,field_id,measure,value FROM fact.acs_bulk_estimate estimate "
                "JOIN core.geography geography USING (geography_id) "
                "WHERE source_artifact_id=(SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s) "
                "ORDER BY geography.geoid,field_id",
                (key,),
            )
            self.assertEqual(
                cur.fetchall(),
                [
                    {
                        "geoid": "99",
                        "field_id": "B25001_E001",
                        "measure": "estimate",
                        "value": __import__("decimal").Decimal("200"),
                    },
                    {
                        "geoid": "99",
                        "field_id": "B25001_E002",
                        "measure": "estimate",
                        "value": None,
                    },
                    {
                        "geoid": "99",
                        "field_id": "B25001_M001",
                        "measure": "margin_of_error",
                        "value": __import__("decimal").Decimal("9"),
                    },
                    {
                        "geoid": "99",
                        "field_id": "B25001_M002",
                        "measure": "margin_of_error",
                        "value": __import__("decimal").Decimal("4"),
                    },
                    {
                        "geoid": "99001",
                        "field_id": "B25001_E001",
                        "measure": "estimate",
                        "value": __import__("decimal").Decimal("100"),
                    },
                    {
                        "geoid": "99001",
                        "field_id": "B25001_E002",
                        "measure": "estimate",
                        "value": None,
                    },
                    {
                        "geoid": "99001",
                        "field_id": "B25001_M001",
                        "measure": "margin_of_error",
                        "value": __import__("decimal").Decimal("7"),
                    },
                    {
                        "geoid": "99001",
                        "field_id": "B25001_M002",
                        "measure": "margin_of_error",
                        "value": None,
                    },
                ],
            )
        self._remove_artifact(key)

    def test_pep_generated_csv_stages_and_loads_all_vintage_years(self) -> None:
        key = "pep-2020-2025-state-totals"
        self._remove_artifact(key)
        path = Path(self.temp.name) / "pep.csv"
        with path.open("w", newline="") as output:
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "SUMLEV",
                    "STATE",
                    "NAME",
                    *[f"POPESTIMATE{year}" for year in range(2020, 2026)],
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "SUMLEV": "040",
                    "STATE": "99",
                    "NAME": "Integration State",
                    **{f"POPESTIMATE{year}": str(year) for year in range(2020, 2026)},
                }
            )
        self._register("census.population_estimates", key, path)
        plan = {
            "state": "downloaded",
            "selection": {"vintage": "2020-2025", "release_year": 2025},
            "canonical_load_scope": {"geography_levels": ["state"]},
        }
        self.assertEqual(stage_pep(plan), 1)
        plan["state"] = "staged"
        self.assertEqual(load_pep(plan), 6)
        load_pep(plan)
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM fact.population_estimate WHERE source_artifact_id=(SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s)",
                (key,),
            )
            self.assertEqual(cur.fetchone()["count"], 6)
        self._remove_artifact(key)

    def test_dhc_generated_geo_segments_and_matrix_load_idempotently(self) -> None:
        archive_key, matrix_key = "dhc-2020-national", "dhc-2020-table-matrix"
        self._remove_artifact(archive_key)
        self._remove_artifact(matrix_key)
        archive_path = Path(self.temp.name) / "dhc.zip"
        geo = ["DHCST", "ZZ", "040", "00", "00", "000", "00", "0000001", "0400000US99"]
        segment_1 = ["DHCST", "ZZ", "000", "01", "0000001", "17"]
        segment_5 = ["DHCST", "ZZ", "000", "05", "0000001", "23"]
        with ZipFile(archive_path, "w") as archive:
            archive.writestr("usgeo2020.dhc", "|".join(geo) + "\n")
            archive.writestr("us000012020.dhc", "|".join(segment_1) + "\n")
            archive.writestr("us000052020.dhc", "|".join(segment_5) + "\n")
        matrix_path = Path(self.temp.name) / "matrix.xlsx"
        import openpyxl

        book = openpyxl.Workbook()
        sheet = book.active
        sheet.title = "DHC Table Matrix"
        sheet.append(["title"] * 4)
        sheet.append(["headers"] * 4)
        sheet.append([None, "H1", "H0010001", 1])
        sheet.append([None, "P1", "P0010001", 5])
        book.save(matrix_path)
        self._register("census.decennial", archive_key, archive_path)
        self._register("census.decennial", matrix_key, matrix_path)
        plan = {
            "state": "downloaded",
            "canonical_load_scope": {"summary_levels": ["040"], "tables": ["H1", "P1"]},
        }
        self.assertEqual(stage_dhc(plan), 1)
        plan["state"] = "staged"
        self.assertEqual(load_dhc(plan), 2)
        load_dhc(plan)
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT table_id,value FROM fact.decennial_dhc_value WHERE source_artifact_id=(SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s) ORDER BY table_id",
                (archive_key,),
            )
            self.assertEqual(
                cur.fetchall(),
                [{"table_id": "H1", "value": 17}, {"table_id": "P1", "value": 23}],
            )
        self._remove_artifact(archive_key)
        self._remove_artifact(matrix_key)

    def test_tiger_generated_shapefile_stages_and_loads_idempotently(self) -> None:
        try:
            import geopandas
            from shapely.geometry import Polygon
        except ImportError:
            self.skipTest("TIGER integration requires the spatial extra")
        key = "integration-tiger-state"
        self._remove_artifact(key)
        source = Path(self.temp.name) / "state.shp"
        frame = geopandas.GeoDataFrame(
            {"GEOID": ["99"], "NAME": ["Integration State"], "STATEFP": ["99"]},
            geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])],
            crs="EPSG:4269",
        )
        frame.to_file(source, driver="ESRI Shapefile")
        archive_path = Path(self.temp.name) / "state.zip"
        with ZipFile(archive_path, "w") as archive:
            for member in source.parent.glob("state.*"):
                archive.write(member, member.name)
        self._register("census.tiger", key, archive_path)
        plan = {
            "state": "downloaded",
            "selection": {"boundary_vintage": 2020},
            "canonical_load_scope": {"layers": ["state"]},
            "artifacts": [{"artifact_key": key, "kind": "state"}],
        }
        self.assertEqual(stage_tiger(plan), 1)
        plan["state"] = "staged"
        self.assertEqual(load_tiger(plan), 1)
        load_tiger(plan)
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM core.geography_boundary boundary JOIN core.geography geography USING (geography_id) WHERE geography.geography_type='state' AND geography.geoid='99' AND boundary.boundary_vintage=2020 AND boundary.source_artifact_id=(SELECT artifact_id FROM ingest.artifact WHERE artifact_key=%s)",
                (key,),
            )
            self.assertEqual(cur.fetchone()["count"], 1)
        self._remove_artifact(key)

    def test_tiger_load_scopes_geography_to_its_own_plan_across_vintages(
        self,
    ) -> None:
        # Confirmed live (2016 vs. 2020): the same CBSA geoid can be renamed
        # between TIGER vintages (e.g. a metro area's title component
        # changes). Before this was fixed, load_tiger's geography upsert
        # pulled from every vintage ever staged into stage.tiger_feature
        # (no per-plan scoping), so a second vintage with a renamed geoid
        # crashed with "ON CONFLICT DO UPDATE cannot affect row a second
        # time" instead of loading cleanly.
        try:
            import geopandas
            from shapely.geometry import Polygon
        except ImportError:
            self.skipTest("TIGER integration requires the spatial extra")

        def _cbsa_archive(name: str, path: Path) -> Path:
            shp = path / "cbsa.shp"
            geopandas.GeoDataFrame(
                {"GEOID": ["99999"], "NAME": [name]},
                geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])],
                crs="EPSG:4269",
            ).to_file(shp, driver="ESRI Shapefile")
            archive_path = path / "cbsa.zip"
            with ZipFile(archive_path, "w") as archive:
                for member in shp.parent.glob("cbsa.*"):
                    archive.write(member, member.name)
            return archive_path

        old_key, new_key = "integration-tiger-cbsa-old", "integration-tiger-cbsa-new"
        self._remove_artifact(old_key)
        self._remove_artifact(new_key)
        old_dir = Path(self.temp.name) / "old"
        new_dir = Path(self.temp.name) / "new"
        old_dir.mkdir()
        new_dir.mkdir()
        self._register(
            "census.tiger", old_key, _cbsa_archive("Old Metro Name, ST", old_dir)
        )
        self._register(
            "census.tiger", new_key, _cbsa_archive("New Metro Name, ST", new_dir)
        )
        old_plan = {
            "state": "downloaded",
            "selection": {"boundary_vintage": 2016},
            "canonical_load_scope": {"layers": ["cbsa"]},
            "artifacts": [{"artifact_key": old_key, "kind": "cbsa"}],
        }
        new_plan = {
            "state": "downloaded",
            "selection": {"boundary_vintage": 2020},
            "canonical_load_scope": {"layers": ["cbsa"]},
            "artifacts": [{"artifact_key": new_key, "kind": "cbsa"}],
        }
        self.assertEqual(stage_tiger(old_plan), 1)
        self.assertEqual(stage_tiger(new_plan), 1)
        old_plan["state"] = new_plan["state"] = "staged"
        self.assertEqual(load_tiger(old_plan), 1)
        self.assertEqual(load_tiger(new_plan), 1)
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM core.geography_boundary boundary JOIN core.geography geography USING (geography_id) WHERE geography.geography_type='cbsa' AND geography.geoid='99999'"
            )
            self.assertEqual(cur.fetchone()["count"], 2)
        self._remove_artifact(old_key)
        self._remove_artifact(new_key)
