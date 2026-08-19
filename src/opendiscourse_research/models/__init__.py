"""Public typed persistence mappings and legacy-table references."""

from .catalog import (
    Basket,
    BasketItem,
    CatalogSnapshot,
    Dataset,
    DatasetField,
    Discovery,
    Plan,
    Provider,
    Resource,
    ResourceField,
    SnapshotResource,
)
from .core import (
    bill_identifier_table,
    bill_table,
    geography_boundary_table,
    geography_table,
    jurisdiction_table,
    legislative_session_table,
    measurement_table,
)
from .ingest import (
    cursor_table,
    identity_exception_table,
    raw_payload_table,
    resume_cursor_table,
    run_table,
)

__all__ = [
    "Basket",
    "BasketItem",
    "CatalogSnapshot",
    "Dataset",
    "DatasetField",
    "Discovery",
    "Plan",
    "Provider",
    "Resource",
    "ResourceField",
    "SnapshotResource",
    "cursor_table",
    "identity_exception_table",
    "bill_identifier_table",
    "bill_table",
    "geography_boundary_table",
    "geography_table",
    "jurisdiction_table",
    "legislative_session_table",
    "measurement_table",
    "raw_payload_table",
    "resume_cursor_table",
    "run_table",
]
