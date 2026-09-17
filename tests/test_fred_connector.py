"""FRED registers as a Connector instead of a plans.py elif."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import MagicMock, patch

from opendiscourse_research.ingestion.connector import (
    Connector,
    ConnectorContext,
    run_connector,
)
from opendiscourse_research.ingestion.connectors import get, handlers, register
from opendiscourse_research.ingestion.fred import FredCoreConnector
from opendiscourse_research.plans import (
    HANDLERS,
    _check_dual_registration,
    execute_handler,
    run_plan,
    validate_plans,
)
from opendiscourse_research.registry import sync as registry_sync


class TestFredConnectorRegistry(unittest.TestCase):
    def test_fred_core_is_not_in_legacy_handlers(self) -> None:
        self.assertNotIn("fred_core", HANDLERS)
        self.assertFalse(HANDLERS & handlers())

    def test_fred_core_is_registered_as_connector(self) -> None:
        connector = get("fred_core")
        self.assertIsNotNone(connector)
        self.assertIsInstance(connector, Connector)
        self.assertIsInstance(connector, FredCoreConnector)
        self.assertIn("fred_core", handlers())
        self.assertEqual(connector.source_id, "fred.series")
        self.assertIsNot(connector, get("fred_core"))

    def test_reviewed_plans_still_validate(self) -> None:
        self.assertEqual(validate_plans(), [])

    def test_run_plan_and_execute_handler_have_no_fred_core_branch(self) -> None:
        self.assertNotIn("fred_core", inspect.getsource(run_plan))
        self.assertNotIn("fred_core", inspect.getsource(execute_handler))

    def test_duplicate_register_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            register("fred_core", FredCoreConnector)

    def test_register_rejects_legacy_handler_name(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "already registered as a legacy handler"):
            register("acs_housing", FredCoreConnector)

    def test_dual_registration_check_raises_when_overlap_exists(self) -> None:
        with patch(
            "opendiscourse_research.plans.connector_handlers",
            return_value=frozenset({"acs_housing"}),
        ):
            with self.assertRaisesRegex(RuntimeError, "Handler.*registered as both"):
                _check_dual_registration()

    @patch("opendiscourse_research.plans.run_connector")
    @patch("opendiscourse_research.plans.bootstrap_housing")
    def test_dispatch_boundary_selects_connector_path(
        self, mock_bootstrap: MagicMock, mock_run_connector: MagicMock
    ) -> None:
        mock_run_connector.return_value = ConnectorContext(
            source_id="fred.series", extras={"count": 5, "failures": {}}
        )
        count, failures = execute_handler(
            {
                "id": "fredcore",
                "handler": "fred_core",
                "parameters": {"max_priority": 1},
            }
        )
        mock_run_connector.assert_called_once()
        mock_bootstrap.assert_not_called()
        self.assertEqual(count, 5)
        self.assertEqual(failures, {})

    def test_register_rejects_non_connector(self) -> None:
        class Incomplete:
            source_id = "nope"

        with self.assertRaises(TypeError):
            register("not_a_connector", Incomplete)

    def test_unknown_handler_is_not_registered(self) -> None:
        self.assertIsNone(get("not_a_handler"))

    def test_execute_handler_fredcore_uses_connector_and_manifest(self) -> None:
        with patch(
            "opendiscourse_research.ingestion.fred.ingest_manifest",
            return_value=({"DGS10": 3}, {}),
        ) as mocked:
            count, failures = execute_handler(
                {
                    "id": "fredcore",
                    "handler": "fred_core",
                    "parameters": {"max_priority": 1},
                }
            )
        mocked.assert_called_once_with(category=None, priority=1, report=None)
        self.assertEqual(count, 3)
        self.assertEqual(failures, {})

    def test_execute_handler_fredcore_surfaces_failed_series(self) -> None:
        with patch(
            "opendiscourse_research.ingestion.fred.ingest_manifest",
            return_value=({"DGS10": 1}, {"DGS2": "boom"}),
        ):
            count, failures = execute_handler(
                {
                    "id": "fredcore",
                    "handler": "fred_core",
                    "parameters": {"max_priority": 1},
                }
            )
        self.assertEqual(count, 1)
        self.assertEqual(failures, {"DGS2": "boom"})

    def test_discover_index_does_not_ingest_observations(self) -> None:
        indexed = {"state": "paused", "statistics": {"series": 4}, "run_pages": 1}
        with (
            patch(
                "opendiscourse_research.providers.fred.index_batch",
                return_value=indexed,
            ) as index_batch,
            patch(
                "opendiscourse_research.ingestion.fred.ingest_manifest",
            ) as manifest,
        ):
            ctx = run_connector(
                FredCoreConnector(),
                ConnectorContext(
                    source_id="fred.series",
                    extras={"index_pages": 1, "index_seconds": None},
                ),
            )
        index_batch.assert_called_once_with(1, None, None)
        manifest.assert_not_called()
        self.assertEqual(ctx.extras["phase"], "discover")
        self.assertEqual(ctx.extras["count"], 4)
        self.assertEqual(ctx.extras["discovery"], indexed)

    def test_discover_catalog_does_not_ingest_observations(self) -> None:
        catalog = {"resources": 12, "state": "synced"}
        with (
            patch(
                "opendiscourse_research.browser.sync_fred",
                return_value=catalog,
            ) as sync_fred,
            patch(
                "opendiscourse_research.ingestion.fred.ingest_manifest",
            ) as manifest,
        ):
            ctx = run_connector(
                FredCoreConnector(),
                ConnectorContext(
                    source_id="fred.series",
                    extras={"catalog": True, "refresh": False},
                ),
            )
        sync_fred.assert_called_once_with(False)
        manifest.assert_not_called()
        self.assertEqual(ctx.extras["phase"], "discover")
        self.assertEqual(ctx.extras["discovery"], catalog)
        self.assertEqual(ctx.extras["count"], 12)

    def test_discover_full_and_preview_skip_observations(self) -> None:
        full = {"state": "synced", "resources": 9, "series_memberships": 11}
        preview = {"state": "preview", "series_memberships": 7}
        with (
            patch(
                "opendiscourse_research.browser.sync_fred_full",
                return_value=full,
            ) as sync_full,
            patch(
                "opendiscourse_research.ingestion.fred.ingest_manifest",
            ) as manifest,
        ):
            ctx = run_connector(
                FredCoreConnector(),
                ConnectorContext(source_id="fred.series", extras={"full": True}),
            )
        sync_full.assert_called_once()
        manifest.assert_not_called()
        self.assertEqual(ctx.extras["count"], 9)
        with (
            patch(
                "opendiscourse_research.browser.preview_fred_full",
                return_value=preview,
            ) as preview_full,
            patch(
                "opendiscourse_research.ingestion.fred.ingest_manifest",
            ) as manifest,
        ):
            ctx = run_connector(
                FredCoreConnector(),
                ConnectorContext(
                    source_id="fred.series",
                    extras={"full": True, "preview": True},
                ),
            )
        preview_full.assert_called_once()
        manifest.assert_not_called()
        self.assertEqual(ctx.extras["count"], 7)

    def test_discover_failure_skips_observations(self) -> None:
        with (
            patch(
                "opendiscourse_research.providers.fred.index_batch",
                side_effect=ValueError("already running"),
            ),
            patch(
                "opendiscourse_research.ingestion.fred.ingest_manifest",
            ) as manifest,self.assertRaises(ValueError)
        ):
            run_connector(
                FredCoreConnector(),
                ConnectorContext(
                    source_id="fred.series",
                    extras={"index_pages": 1},
                ),
            )
        manifest.assert_not_called()

    def test_registry_sync_fred_has_no_provider_elif(self) -> None:
        source = inspect.getsource(registry_sync)
        self.assertNotIn("index_batch", source)
        self.assertNotIn("sync_fred_full", source)
        self.assertNotIn("preview_fred_full", source)
        self.assertIn("run_connector", source)
        self.assertIn("fred_core", source)

    def test_registry_sync_index_uses_connector_and_returns_early(self) -> None:
        discovery = {"state": "paused", "statistics": {"series": 2}}
        with patch(
            "opendiscourse_research.registry.run_connector",
            return_value=ConnectorContext(
                source_id="fred.series",
                extras={"discovery": discovery, "count": 2, "phase": "discover"},
            ),
        ) as runner:
            result = registry_sync(
                sources={"fred", "bls"},
                index_pages=1,
                index_seconds=None,
            )
        runner.assert_called_once()
        extras = runner.call_args.args[1].extras
        self.assertEqual(extras["index_pages"], 1)
        self.assertIsNone(extras["index_seconds"])
        self.assertEqual(result["results"]["fred"], discovery)
        self.assertNotIn("bls", result["results"])

    def test_registry_sync_index_drives_real_connector(self) -> None:
        indexed = {"state": "paused", "statistics": {"series": 3}}
        with (
            patch(
                "opendiscourse_research.providers.fred.index_batch",
                return_value=indexed,
            ) as index_batch,
            patch(
                "opendiscourse_research.ingestion.fred.ingest_manifest",
            ) as manifest,
        ):
            result = registry_sync(sources={"fred"}, index_pages=2)
        index_batch.assert_called_once_with(2, None, None)
        manifest.assert_not_called()
        self.assertEqual(result["results"]["fred"], indexed)

    def test_registry_sync_index_seconds_forwards_budget(self) -> None:
        indexed = {"state": "paused", "statistics": {"series": 1}}
        with patch(
            "opendiscourse_research.providers.fred.index_batch",
            return_value=indexed,
        ) as index_batch:
            registry_sync(sources={"fred"}, index_pages=None, index_seconds=30)
        index_batch.assert_called_once_with(None, 30, None)

    def test_registry_sync_current_snapshot_skips_connector(self) -> None:
        with (
            patch(
                "opendiscourse_research.registry._has_snapshot",
                return_value=True,
            ),
            patch("opendiscourse_research.registry.run_connector") as runner,
        ):
            result = registry_sync(sources={"fred"}, refresh=False)
        runner.assert_not_called()
        self.assertEqual(result["results"]["fred"], {"state": "current"})

    def test_registry_sync_refresh_forwards_catalog(self) -> None:
        catalog = {"resources": 5, "state": "synced"}
        with (
            patch(
                "opendiscourse_research.browser.sync_fred",
                return_value=catalog,
            ) as sync_fred,
            patch(
                "opendiscourse_research.ingestion.fred.ingest_manifest",
            ) as manifest,
        ):
            result = registry_sync(sources={"fred"}, refresh=True)
        sync_fred.assert_called_once_with(True)
        manifest.assert_not_called()
        self.assertEqual(result["results"]["fred"], catalog)

    def test_execute_handler_requires_count_after_checkpoint(self) -> None:
        class Silent:
            source_id = "silent.source"

            def discover(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def select(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def plan(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def extract(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def stage(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def validate(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def publish(self, ctx: ConnectorContext) -> ConnectorContext:
                return ctx

            def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
                return ConnectorContext(source_id=self.source_id)

        with patch(
            "opendiscourse_research.plans.get_connector",
            return_value=Silent(),
        ), self.assertRaises(ValueError):
            execute_handler(
                {
                    "id": "silent",
                    "handler": "silent",
                    "parameters": {},
                }
            )
