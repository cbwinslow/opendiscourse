"""SQLModel mappings for the Alembic-owned ``catalog`` schema."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlmodel import Field, SQLModel


def _json_object_column() -> Column[dict[str, Any]]:
    """Return the canonical non-null JSON object column used by catalog rows."""
    return Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))


_timestamp = DateTime(timezone=True)

# ``catalog.resource`` preserves a foreign key to immutable ingest evidence.
# The owned model slice does not map ``ingest.artifact`` yet, but SQLAlchemy
# needs a lightweight target table to order and render that foreign key.
_artifact = Table(
    "artifact",
    SQLModel.metadata,
    Column("artifact_id", PostgreSQLUUID(as_uuid=True), primary_key=True),
    Column("dataset_id", Text, nullable=False),
    Column("remote_url", Text, nullable=False),
    Column("artifact_key", Text, nullable=False),
    Column("checksum_sha256", Text, nullable=False),
    schema="ingest",
    info={"alembic_exclude": True},
)


def artifact_table() -> Table:
    """Return the read-only ingest artifact reference used by catalog provenance."""
    return _artifact


class Provider(SQLModel, table=True):
    """An upstream organization that publishes one or more datasets."""

    __tablename__ = "provider"
    __table_args__ = {"schema": "catalog"}

    provider_id: str = Field(sa_column=Column(Text, primary_key=True))
    name: str = Field(sa_column=Column(Text, nullable=False))
    base_url: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )


class Dataset(SQLModel, table=True):
    """A registered dataset and its operational metadata."""

    __tablename__ = "dataset"
    __table_args__ = {"schema": "catalog"}

    dataset_id: str = Field(sa_column=Column(Text, primary_key=True))
    provider_id: str = Field(
        sa_column=Column(
            Text, ForeignKey("catalog.provider.provider_id"), nullable=False
        )
    )
    title: str = Field(sa_column=Column(Text, nullable=False))
    access_method: str | None = Field(default=None, sa_column=Column(Text))
    grain_description: str | None = Field(default=None, sa_column=Column(Text))
    refresh_cadence: str | None = Field(default=None, sa_column=Column(Text))
    priority: int | None = Field(default=None, sa_column=Column(SmallInteger))
    active: bool = Field(
        default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true"))
    )
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=_json_object_column()
    )
    created_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )


class DatasetField(SQLModel, table=True):
    """A versioned field definition published by a dataset."""

    __tablename__ = "dataset_field"
    __table_args__ = {"schema": "catalog"}

    dataset_id: str = Field(
        sa_column=Column(
            Text, ForeignKey("catalog.dataset.dataset_id"), primary_key=True
        )
    )
    field_id: str = Field(sa_column=Column(Text, primary_key=True))
    valid_from: date = Field(sa_column=Column(Date, primary_key=True, nullable=False))
    label: str | None = Field(default=None, sa_column=Column(Text))
    data_type: str | None = Field(default=None, sa_column=Column(Text))
    description: str | None = Field(default=None, sa_column=Column(Text))
    valid_to: date | None = Field(default=None, sa_column=Column(Date))
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=_json_object_column()
    )


class Resource(SQLModel, table=True):
    """A provider-published resource available for discovery or selection."""

    __tablename__ = "resource"
    __table_args__ = (
        Index("resource_search_idx", "dataset_id", "release_year", "resource_type"),
        Index(
            "resource_title_trgm_idx",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "resource_fts_idx",
            text(
                "to_tsvector('english', coalesce(resource_key, '') || ' ' || "
                "coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || "
                "coalesce(universe, '') || ' ' || coalesce(resource_type, '') || ' ' || "
                "coalesce(metadata::text, ''))"
            ),
            postgresql_using="gin",
        ),
        UniqueConstraint("dataset_id", "resource_key"),
        {"schema": "catalog"},
    )

    resource_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    dataset_id: str = Field(
        sa_column=Column(
            Text, ForeignKey("catalog.dataset.dataset_id"), nullable=False
        )
    )
    resource_key: str = Field(sa_column=Column(Text, nullable=False))
    resource_type: str = Field(sa_column=Column(Text, nullable=False))
    title: str = Field(sa_column=Column(Text, nullable=False))
    summary: str | None = Field(default=None, sa_column=Column(Text))
    universe: str | None = Field(default=None, sa_column=Column(Text))
    release_year: int | None = Field(default=None, sa_column=Column(Integer))
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=_json_object_column()
    )
    source_artifact_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            ForeignKey("ingest.artifact.artifact_id"),
            nullable=True,
        ),
    )
    discovered_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )


class ResourceField(SQLModel, table=True):
    """A field within one provider-published catalog resource."""

    __tablename__ = "resource_field"
    __table_args__ = {"schema": "catalog"}

    resource_id: UUID = Field(
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            ForeignKey("catalog.resource.resource_id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    field_key: str = Field(sa_column=Column(Text, primary_key=True))
    label: str | None = Field(default=None, sa_column=Column(Text))
    description: str | None = Field(default=None, sa_column=Column(Text))
    data_type: str | None = Field(default=None, sa_column=Column(Text))
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=_json_object_column()
    )
    discovered_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )


class Basket(SQLModel, table=True):
    """A reviewed set of catalog resources selected for a proposed workflow."""

    __tablename__ = "basket"
    __table_args__ = (
        CheckConstraint(
            "state IN ('draft', 'review', 'approved', 'archived')",
            name="basket_state_check",
        ),
        {"schema": "catalog"},
    )

    basket_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    name: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    state: str = Field(
        default="draft", sa_column=Column(Text, nullable=False, server_default=text("'draft'"))
    )
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=_json_object_column()
    )
    created_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )
    updated_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )


class BasketItem(SQLModel, table=True):
    """One resource selected into a basket with optional field selection."""

    __tablename__ = "basket_item"
    __table_args__ = {"schema": "catalog"}

    basket_id: UUID = Field(
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            ForeignKey("catalog.basket.basket_id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    resource_id: UUID = Field(
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            ForeignKey("catalog.resource.resource_id", ondelete="RESTRICT"),
            primary_key=True,
        )
    )
    selected_fields: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    )
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=_json_object_column()
    )
    added_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )


class CatalogSnapshot(SQLModel, table=True):
    """Immutable checksum-addressed evidence for one catalog discovery result."""

    __tablename__ = "snapshot"
    __table_args__ = (
        UniqueConstraint("dataset_id", "checksum_sha256"),
        {"schema": "catalog"},
    )

    snapshot_id: UUID | None = Field(
        default=None,
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            primary_key=True,
            server_default=text("gen_random_uuid()"),
        ),
    )
    dataset_id: str = Field(
        sa_column=Column(Text, ForeignKey("catalog.dataset.dataset_id"), nullable=False)
    )
    source_url: str = Field(sa_column=Column(Text, nullable=False))
    checksum_sha256: str = Field(sa_column=Column(Text, nullable=False))
    artifact_id: UUID | None = Field(
        default=None,
        sa_column=Column(PostgreSQLUUID(as_uuid=True), ForeignKey("ingest.artifact.artifact_id")),
    )
    captured_at: datetime | None = Field(
        default=None, sa_column=Column(_timestamp, nullable=False, server_default=text("now()"))
    )
    metadata_: dict[str, Any] = Field(default_factory=dict, sa_column=_json_object_column())


class SnapshotResource(SQLModel, table=True):
    """The resources represented by one immutable catalog snapshot."""

    __tablename__ = "snapshot_resource"
    __table_args__ = {"schema": "catalog"}

    snapshot_id: UUID = Field(
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            ForeignKey("catalog.snapshot.snapshot_id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    resource_id: UUID = Field(
        sa_column=Column(
            PostgreSQLUUID(as_uuid=True),
            ForeignKey("catalog.resource.resource_id", ondelete="RESTRICT"),
            primary_key=True,
        )
    )
