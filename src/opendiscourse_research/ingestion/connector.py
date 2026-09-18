"""Typed Connector lifecycle for adding a source without dispatcher branches.

Story 2.1: the protocol and an ordered runner. FRED registration is 2.2;
end-to-end FRED migration is 2.3. Adapters must not add ``if``/``elif`` to
``cli.py``, ``plans.py`` ``run_plan()``, or ``registry.sync``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

STAGES: tuple[str, ...] = (
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
)


@dataclass
class ConnectorContext:
    """Shared state passed through every Connector stage."""

    source_id: str
    selected_ids: tuple[str, ...] = ()
    plan_id: str | None = None
    artifact_urls: tuple[str, ...] = ()
    checksums: tuple[str, ...] = ()
    run_id: str | None = None
    cursor: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@runtime_checkable
class Connector(Protocol):
    """One source family, ten stages. Structural — do not require a base class."""

    source_id: str

    def discover(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def select(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def plan(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def extract(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def evidence(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def stage(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def normalize(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def validate(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def publish(self, ctx: ConnectorContext) -> ConnectorContext: ...
    def checkpoint(self, ctx: ConnectorContext) -> ConnectorContext: ...


def _call_stage(
    connector: Connector, name: str, ctx: ConnectorContext
) -> ConnectorContext:
    result = getattr(connector, name)(ctx)
    if not isinstance(result, ConnectorContext):
        raise TypeError(f"{connector.source_id}.{name} must return ConnectorContext")
    if result.source_id != connector.source_id:
        raise ValueError(
            f"{connector.source_id}.{name} changed source_id to {result.source_id!r}"
        )
    return result


def run_connector(
    connector: Connector, ctx: ConnectorContext | None = None
) -> ConnectorContext:
    """Run ``STAGES`` in order, always ending in ``checkpoint``.

    Earlier stages run until the first exception. ``checkpoint`` still runs
    in ``finally`` so adapters can persist an actionable resume cursor.
    """
    if not isinstance(connector, Connector):
        raise TypeError(f"{type(connector).__name__} does not implement Connector")
    if ctx is None:
        ctx = ConnectorContext(source_id=connector.source_id)
    elif ctx.source_id != connector.source_id:
        raise ValueError(
            f"Context source_id {ctx.source_id!r} does not match "
            f"connector {connector.source_id!r}"
        )
    try:
        for name in STAGES:
            if name == "checkpoint":
                continue
            ctx = _call_stage(connector, name, ctx)
    except Exception as exc:
        ctx.error = str(exc)
        raise
    finally:
        ctx = _call_stage(connector, "checkpoint", ctx)
    return ctx
