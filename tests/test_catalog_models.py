"""Regression coverage for the Alembic-owned catalog SQLModel mappings."""

from opendiscourse_research import models
from opendiscourse_research.models.catalog import (
    Basket,
    BasketItem,
    Dataset,
    DatasetField,
    Discovery,
    Plan,
    Provider,
    Resource,
    ResourceField,
)


def test_catalog_models_preserve_legacy_table_and_column_names() -> None:
    """Python-safe attributes must not rename established catalog columns."""
    expected = {
        "catalog.provider": Provider,
        "catalog.dataset": Dataset,
        "catalog.dataset_field": DatasetField,
        "catalog.plan": Plan,
        "catalog.discovery": Discovery,
        "catalog.resource": Resource,
        "catalog.resource_field": ResourceField,
        "catalog.basket": Basket,
        "catalog.basket_item": BasketItem,
    }

    assert {model.__table__.fullname: model for model in expected.values()} == expected
    for model in (
        Dataset,
        DatasetField,
        Resource,
        ResourceField,
        Basket,
        BasketItem,
    ):
        assert "metadata" in model.__table__.c
        assert "metadata_" not in model.__table__.c


def test_catalog_models_preserve_catalog_constraints_and_indexes() -> None:
    """The baseline metadata retains idempotency and selection integrity rules."""
    basket_constraints = {constraint.name for constraint in Basket.__table__.constraints}

    assert any(
        tuple(column.name for column in constraint.columns)
        == ("dataset_id", "resource_key")
        for constraint in Resource.__table__.constraints
        if hasattr(constraint, "columns")
    )
    assert "basket_state_check" in basket_constraints
    assert "resource_search_idx" in {index.name for index in Resource.__table__.indexes}


def test_public_models_module_exposes_typed_persistence_boundaries() -> None:
    """Callers can use new mappings without importing private implementation modules."""
    assert models.Plan is Plan
    assert models.Discovery is Discovery
    assert models.geography_table().fullname == "core.geography"
    assert models.measurement_table().fullname == "fact.measurement"
    assert models.geography_boundary_table().fullname == "core.geography_boundary"
    assert models.run_table().fullname == "ingest.run"
    assert models.raw_payload_table().fullname == "ingest.raw_payload"
    assert models.cursor_table().fullname == "ingest.cursor"
