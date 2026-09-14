"""Handler → Connector registry.

Register a Connector class here instead of adding ``HANDLERS`` members or
``run_plan()`` elif branches. Lookup key is the inventory plan ``handler``.
``get`` constructs a new instance per call so adapters stay unshared.
"""

from __future__ import annotations

from .connector import Connector

_CONNECTORS: dict[str, type[Connector]] = {}


def register(handler: str, connector_type: type[Connector]) -> None:
    """Bind an inventory handler name to a Connector class."""
    if handler in _CONNECTORS:
        raise ValueError(f"handler {handler!r} is already registered")
    probe = connector_type()
    if not isinstance(probe, Connector):
        raise TypeError(f"{connector_type.__name__} does not implement Connector")
    _CONNECTORS[handler] = connector_type


def get(handler: str) -> Connector | None:
    """Return a new Connector for ``handler``, if registered."""
    connector_type = _CONNECTORS.get(handler)
    if connector_type is None:
        return None
    return connector_type()


def handlers() -> frozenset[str]:
    """Inventory handler names served by Connectors."""
    return frozenset(_CONNECTORS)


def _register_builtins() -> None:
    from .fred import FredCoreConnector

    register("fred_core", FredCoreConnector)


_register_builtins()
