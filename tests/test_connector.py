"""Connector protocol: ten stages, ordered runner, no dispatcher coupling."""

from __future__ import annotations

import ast
import inspect
import unittest

from opendiscourse_research.ingestion.connector import (
    STAGES,
    Connector,
    ConnectorContext,
    run_connector,
)


class _RecordingConnector:
    source_id = "test.source"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _step(self, name: str, ctx: ConnectorContext) -> ConnectorContext:
        self.calls.append(name)
        trace = list(ctx.extras.get("trace", ()))
        trace.append(name)
        return ConnectorContext(
            source_id=ctx.source_id,
            selected_ids=ctx.selected_ids,
            plan_id=ctx.plan_id,
            artifact_urls=ctx.artifact_urls,
            checksums=ctx.checksums,
            run_id=ctx.run_id,
            cursor=dict(ctx.cursor),
            extras={"trace": trace},
            error=ctx.error,
        )

    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("discover", ctx)

    def select(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("select", ctx)

    def plan(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("plan", ctx)

    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("extract", ctx)

    def evidence(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("evidence", ctx)

    def stage(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("stage", ctx)

    def normalize(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("normalize", ctx)

    def validate(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("validate", ctx)

    def publish(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("publish", ctx)

    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext:
        return self._step("checkpoint", ctx)


class _Incomplete:
    source_id = "incomplete"

    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        return ctx


class _NoSourceId:
    def discover(self, ctx: ConnectorContext) -> ConnectorContext:
        return ctx


class _BadReturn:
    source_id = "bad.return"

    def __getattr__(self, name: str):
        if name in STAGES:
            return lambda ctx: None
        raise AttributeError(name)


class _FailingExtract(_RecordingConnector):
    def extract(self, ctx: ConnectorContext) -> ConnectorContext:
        self._step("extract", ctx)
        raise RuntimeError("provider down")


class TestConnectorProtocol(unittest.TestCase):
    def test_stages_match_architecture_lifecycle(self) -> None:
        self.assertEqual(
            STAGES,
            (
                "discover",
                "select",
                "plan",
                "extract",
                "evidence",
                "stage",
                "normalize",
                "validate",
                "publish",
                "checkpoint",
            ),
        )

    def test_protocol_methods_match_stages(self) -> None:
        annotations = Connector.__annotations__ if hasattr(Connector, "__annotations__") else {}
        del annotations
        for name in STAGES:
            self.assertTrue(callable(getattr(Connector, name, None)), name)

    def test_recording_connector_satisfies_protocol(self) -> None:
        self.assertIsInstance(_RecordingConnector(), Connector)

    def test_missing_stages_are_not_a_connector(self) -> None:
        self.assertNotIsInstance(_Incomplete(), Connector)

    def test_missing_source_id_is_not_a_connector(self) -> None:
        self.assertNotIsInstance(_NoSourceId(), Connector)

    def test_run_connector_rejects_non_protocol(self) -> None:
        with self.assertRaises(TypeError):
            run_connector(_Incomplete())

    def test_run_connector_calls_stages_in_order_and_threads_new_context(self) -> None:
        adapter = _RecordingConnector()
        ctx = run_connector(adapter)
        self.assertEqual(adapter.calls, list(STAGES))
        self.assertEqual(ctx.source_id, "test.source")
        self.assertEqual(ctx.extras["trace"], list(STAGES))
        self.assertIsNot(ctx, ConnectorContext(source_id="test.source"))

    def test_run_connector_rejects_mismatched_source_id(self) -> None:
        adapter = _RecordingConnector()
        with self.assertRaises(ValueError):
            run_connector(adapter, ConnectorContext(source_id="other"))

    def test_run_connector_rejects_non_context_return(self) -> None:
        with self.assertRaises(TypeError):
            run_connector(_BadReturn())

    def test_checkpoint_runs_after_earlier_stage_failure(self) -> None:
        adapter = _FailingExtract()
        with self.assertRaises(RuntimeError):
            run_connector(adapter)
        self.assertEqual(
            adapter.calls,
            ["discover", "select", "plan", "extract", "checkpoint"],
        )

    def test_protocol_module_does_not_import_dispatchers(self) -> None:
        tree = ast.parse(inspect.getsource(inspect.getmodule(run_connector)))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        joined = " ".join(sorted(imported))
        self.assertNotIn("plans", joined)
        self.assertNotIn("cli", joined)
        self.assertNotIn("registry", joined)
