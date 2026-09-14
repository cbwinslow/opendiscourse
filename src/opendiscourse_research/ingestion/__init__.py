"""Provider adapters and common ingestion primitives."""

from .connector import STAGES, Connector, ConnectorContext, run_connector
from .connectors import get, handlers, register

__all__ = [
    "STAGES",
    "Connector",
    "ConnectorContext",
    "get",
    "handlers",
    "register",
    "run_connector",
]
