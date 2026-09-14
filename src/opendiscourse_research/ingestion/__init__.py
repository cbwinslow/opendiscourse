"""Provider adapters and common ingestion primitives."""

from .connector import STAGES, Connector, ConnectorContext, run_connector

__all__ = ["STAGES", "Connector", "ConnectorContext", "run_connector"]
