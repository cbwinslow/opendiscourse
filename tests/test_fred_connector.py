"""FRED registers as a Connector instead of a plans.py elif."""

from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from opendiscourse_research.ingestion.connector import Connector, ConnectorContext
from opendiscourse_research.ingestion.connectors import get, handlers, register
from opendiscourse_research.ingestion.fred import FredCoreConnector
from opendiscourse_research.plans import (
    HANDLERS,
    execute_handler,
    run_plan,
    validate_plans,
)


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
