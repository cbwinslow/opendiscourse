"""Contract tests validating warehouse provenance and identity invariants (Story 1.6 / ADR-0002)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import httpx
import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from opendiscourse_research.catalog import sync_inventory
from opendiscourse_research.config import settings
from opendiscourse_research.db import _engine, apply_migrations, session
from opendiscourse_research.ingestion.base import IngestionRun
from opendiscourse_research.models.catalog import artifact_table
from opendiscourse_research.models.core import (
    document_chunk_table,
    document_table,
    embedding_table,
    geography_boundary_table,
    geography_table,
    member_vote_table,
    membership_table,
    organization_table,
    person_identifier_table,
    person_table,
    roll_call_table,
)
from opendiscourse_research.repositories.legislation import register_artifact


def _psycopg_url(url: str) -> str:
    """Normalize testcontainers' SQLAlchemy URL for the project's psycopg client."""
    return url.replace("postgresql+psycopg2://", "postgresql://", 1)


@pytest.fixture(scope="module")
def catalog_database() -> Iterator[None]:
    """Provide CI's PostGIS service or a local disposable PostGIS instance."""
    original_url = settings.database_url
    external_url = os.environ.get("OPENDISCOURSE_TEST_DATABASE_URL")
    if external_url:
        settings.database_url = external_url
        apply_migrations()
        sync_inventory()
        try:
            yield
        finally:
            settings.database_url = original_url
        return

    postgres = pytest.importorskip("testcontainers.postgres")
    with postgres.PostgresContainer(
        "postgis/postgis:17-3.5",
        username="test",
        password="test",
        dbname="test",
    ) as container:
        settings.database_url = _psycopg_url(container.get_connection_url())
        apply_migrations()
        sync_inventory()
        try:
            yield
        finally:
            settings.database_url = original_url
            _engine.cache_clear()


def _contract_artifact(suffix: str) -> uuid.UUID:
    """Register immutable artifact evidence for contract test scenarios."""
    return register_artifact(
        "census.tiger",
        f"https://example.test/contract-artifact-{suffix}.zip",
        f"/tmp/contract-artifact-{suffix}.zip",
        f"contract-key-{suffix}",
        metadata={"contract": "1.6", "suffix": suffix},
    )["artifact_id"]


def _contract_payload(suffix: str) -> uuid.UUID:
    """Register raw payload evidence for contract test scenarios."""
    response = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        json={"contract": "1.6", "suffix": suffix},
        request=httpx.Request("GET", f"https://example.test/payload/{suffix}"),
    )
    with IngestionRun("fred.series", {"test": True, "suffix": suffix}, mode="plan") as run:
        return run.store_payload(response, {"source": f"payload-{suffix}"})


def _contract_person(suffix: str) -> uuid.UUID:
    """Insert a minimal canonical person for testing."""
    person = person_table()
    with session() as active_session:
        return active_session.execute(
            insert(person)
            .values(full_name=f"Contract Person {suffix}")
            .returning(person.c.person_id)
        ).scalar_one()


def _contract_organization(suffix: str) -> uuid.UUID:
    """Insert a minimal canonical organization for testing."""
    organization = organization_table()
    with session() as active_session:
        return active_session.execute(
            insert(organization)
            .values(organization_type="legislature", name=f"Contract Org {suffix}")
            .returning(organization.c.organization_id)
        ).scalar_one()


def _contract_geography(suffix: str) -> uuid.UUID:
    """Insert a minimal canonical geography for testing."""
    geography = geography_table()
    with session() as active_session:
        return active_session.execute(
            insert(geography)
            .values(
                geography_type=f"state-{suffix}",
                geoid=f"geo-{suffix}",
                name=f"Geography {suffix}",
            )
            .returning(geography.c.geography_id)
        ).scalar_one()


def _contract_roll_call(suffix: str) -> uuid.UUID:
    """Insert a minimal canonical roll call for testing."""
    roll_call = roll_call_table()
    with session() as active_session:
        return active_session.execute(
            insert(roll_call)
            .values(
                jurisdiction=f"us-{suffix}",
                legislative_session=f"session-{suffix}",
                external_id=f"roll-call-{suffix}",
            )
            .returning(roll_call.c.roll_call_id)
        ).scalar_one()


def _contract_document(
    suffix: str,
    *,
    artifact_id: uuid.UUID | None = None,
    payload_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Insert a canonical document with specified evidence references."""
    document = document_table()
    with session() as active_session:
        return active_session.execute(
            insert(document)
            .values(
                document_type="contract_doc",
                source_key=f"doc-{suffix}",
                title=f"Document {suffix}",
                artifact_id=artifact_id,
                source_payload_id=payload_id,
            )
            .returning(document.c.document_id)
        ).scalar_one()


def _contract_chunk(document_id: uuid.UUID, suffix: str) -> uuid.UUID:
    """Insert a document chunk referencing the given document."""
    chunk = document_chunk_table()
    with session() as active_session:
        return active_session.execute(
            insert(chunk)
            .values(
                document_id=document_id,
                ordinal=0,
                text=f"Chunk content {suffix}",
                checksum_sha256=f"hash-{suffix}",
            )
            .returning(chunk.c.chunk_id)
        ).scalar_one()


def test_sourceless_membership_rejected(catalog_database: None) -> None:
    """Class-A core.membership rejects rows missing both artifact and payload evidence."""
    person_id = _contract_person("sourceless-membership")
    org_id = _contract_organization("sourceless-membership")
    membership = membership_table()

    # Reject source-less row
    with pytest.raises(IntegrityError, match="membership_check"), session() as active_session:
        active_session.execute(
            insert(membership).values(
                person_id=person_id,
                organization_id=org_id,
                role="member",
                source_artifact_id=None,
                source_payload_id=None,
            )
        )

    # Accept row with artifact evidence
    artifact_id = _contract_artifact("membership-valid")
    with session() as active_session:
        active_session.execute(
            insert(membership).values(
                person_id=person_id,
                organization_id=org_id,
                role="member",
                source_artifact_id=artifact_id,
            )
        )


def test_sourceless_member_vote_rejected(catalog_database: None) -> None:
    """Class-A fact.member_vote rejects rows missing both artifact and payload evidence."""
    person_id = _contract_person("sourceless-vote")
    roll_call_id = _contract_roll_call("sourceless-vote")
    votes = member_vote_table()

    # Reject source-less row
    with pytest.raises(IntegrityError, match="member_vote_source_evidence"), session() as active_session:
        active_session.execute(
            insert(votes).values(
                roll_call_id=roll_call_id,
                person_id=person_id,
                position="yea",
                source_artifact_id=None,
                source_payload_id=None,
            )
        )

    # Accept row with artifact evidence
    artifact_id = _contract_artifact("vote-valid")
    with session() as active_session:
        active_session.execute(
            insert(votes).values(
                roll_call_id=roll_call_id,
                person_id=person_id,
                position="yea",
                source_artifact_id=artifact_id,
            )
        )


def test_sourceless_geography_boundary_rejected(catalog_database: None) -> None:
    """Class-A core.geography_boundary rejects rows missing both artifact and payload evidence."""
    geography_id = _contract_geography("boundary-check")
    boundary = geography_boundary_table()

    # Reject source-less row
    with pytest.raises(IntegrityError, match="geography_boundary_check"), session() as active_session:
        active_session.execute(
            insert(boundary).values(
                geography_id=geography_id,
                boundary_vintage=2020,
                geom=WKTElement("POINT(-77.0365 38.8977)", srid=4326),
                source_artifact_id=None,
                source_payload_id=None,
            )
        )

    # Accept row with artifact evidence
    artifact_id = _contract_artifact("boundary-valid-artifact")
    with session() as active_session:
        active_session.execute(
            insert(boundary).values(
                geography_id=geography_id,
                boundary_vintage=2020,
                geom=WKTElement("POINT(-77.0365 38.8977)", srid=4326),
                source_artifact_id=artifact_id,
            )
        )

    # Accept row with payload evidence
    payload_id = _contract_payload("boundary-valid-payload")
    with session() as active_session:
        active_session.execute(
            insert(boundary).values(
                geography_id=geography_id,
                boundary_vintage=2021,
                geom=WKTElement("POINT(-77.0365 38.8977)", srid=4326),
                source_payload_id=payload_id,
            )
        )


def test_sourceless_document_rejected(catalog_database: None) -> None:
    """Class-A core.document rejects rows missing both artifact and payload evidence."""
    document = document_table()

    # Reject source-less row
    with pytest.raises(IntegrityError, match="document_check"), session() as active_session:
        active_session.execute(
            insert(document).values(
                document_type="bill_text",
                source_key="sourceless-doc-1",
                title="Sourceless Doc",
                artifact_id=None,
                source_payload_id=None,
            )
        )

    # Accept row with artifact evidence
    artifact_id = _contract_artifact("document-valid-artifact")
    with session() as active_session:
        doc_id_art = active_session.execute(
            insert(document)
            .values(
                document_type="bill_text",
                source_key="valid-doc-artifact",
                title="Artifact Doc",
                artifact_id=artifact_id,
            )
            .returning(document.c.document_id)
        ).scalar_one()
    assert doc_id_art is not None

    # Accept row with payload evidence
    payload_id = _contract_payload("document-valid-payload")
    with session() as active_session:
        doc_id_pay = active_session.execute(
            insert(document)
            .values(
                document_type="bill_text",
                source_key="valid-doc-payload",
                title="Payload Doc",
                source_payload_id=payload_id,
            )
            .returning(document.c.document_id)
        ).scalar_one()
    assert doc_id_pay is not None


def test_duplicate_person_external_id_rejected(catalog_database: None) -> None:
    """Duplicate external identifiers in the same namespace violate uniqueness."""
    person_1_id = _contract_person("dup-id-1")
    person_2_id = _contract_person("dup-id-2")
    identifiers = person_identifier_table()

    with session() as active_session:
        active_session.execute(
            insert(identifiers).values(
                person_id=person_1_id,
                namespace="bioguide",
                external_id="K000001",
            )
        )

    # Inserting the same namespace + external_id for another person must fail
    with pytest.raises(IntegrityError), session() as active_session:
        active_session.execute(
            insert(identifiers).values(
                person_id=person_2_id,
                namespace="bioguide",
                external_id="K000001",
            )
        )


def test_duplicate_artifact_key_rejected(catalog_database: None) -> None:
    """Duplicate artifact keys within the same dataset violate uniqueness."""
    artifacts = artifact_table()
    dataset_id = "census.tiger"
    artifact_key = "tiger-unique-contract-key"

    with session() as active_session:
        active_session.execute(
            insert(artifacts).values(
                dataset_id=dataset_id,
                artifact_key=artifact_key,
                remote_url="https://example.test/tiger-dup-1.zip",
                local_path="/tmp/tiger-dup-1.zip",
                status="planned",
            )
        )

    # Second insert with identical dataset_id and artifact_key must fail
    with pytest.raises(IntegrityError), session() as active_session:
        active_session.execute(
            insert(artifacts).values(
                dataset_id=dataset_id,
                artifact_key=artifact_key,
                remote_url="https://example.test/tiger-dup-2.zip",
                local_path="/tmp/tiger-dup-2.zip",
                status="planned",
            )
        )


def test_embedding_vector_dimensions_mismatch_rejected(catalog_database: None) -> None:
    """Vector cardinality differing from declared dimensions violates embedding_check."""
    artifact_id = _contract_artifact("embedding-test")
    doc_id = _contract_document("embedding-doc", artifact_id=artifact_id)
    chunk_id = _contract_chunk(doc_id, "embed-chunk")
    embeddings = embedding_table()

    # Less dimensions than declared
    with pytest.raises(IntegrityError, match="embedding_check"), session() as active_session:
        active_session.execute(
            insert(embeddings).values(
                chunk_id=chunk_id,
                model="text-embedding-3-small",
                dimensions=3,
                vector_values=[0.1, 0.2],
            )
        )

    # More dimensions than declared
    with pytest.raises(IntegrityError, match="embedding_check"), session() as active_session:
        active_session.execute(
            insert(embeddings).values(
                chunk_id=chunk_id,
                model="text-embedding-3-small",
                dimensions=3,
                vector_values=[0.1, 0.2, 0.3, 0.4],
            )
        )


def test_embedding_vector_dimensions_match_succeeds(catalog_database: None) -> None:
    """Vector cardinality matching declared dimensions is stored successfully."""
    artifact_id = _contract_artifact("embedding-match")
    doc_id = _contract_document("embedding-match-doc", artifact_id=artifact_id)
    chunk_id = _contract_chunk(doc_id, "embed-match-chunk")
    embeddings = embedding_table()

    with session() as active_session:
        embedding_id = active_session.execute(
            insert(embeddings)
            .values(
                chunk_id=chunk_id,
                model="text-embedding-3-small",
                dimensions=3,
                vector_values=[0.1, 0.2, 0.3],
            )
            .returning(embeddings.c.embedding_id)
        ).scalar_one()

    assert embedding_id is not None

    with session() as active_session:
        stored = active_session.execute(
            select(embeddings.c.dimensions, embeddings.c.vector_values).where(
                embeddings.c.embedding_id == embedding_id
            )
        ).mappings().one()

    assert stored["dimensions"] == 3
    assert stored["vector_values"] == [pytest.approx(0.1, 1e-4), pytest.approx(0.2, 1e-4), pytest.approx(0.3, 1e-4)]


def test_historical_tiger_vintages_preserved_without_overwrite(catalog_database: None) -> None:
    """Historical TIGER boundary vintages are preserved side-by-side for the same geography."""
    geography_id = _contract_geography("multi-vintage")
    artifact_id_2020 = _contract_artifact("tiger-2020")
    artifact_id_2024 = _contract_artifact("tiger-2024")
    boundary = geography_boundary_table()

    with session() as active_session:
        active_session.execute(
            insert(boundary).values(
                geography_id=geography_id,
                boundary_vintage=2020,
                geom=WKTElement("POINT(-77.0365 38.8977)", srid=4326),
                source_artifact_id=artifact_id_2020,
            )
        )
        active_session.execute(
            insert(boundary).values(
                geography_id=geography_id,
                boundary_vintage=2024,
                geom=WKTElement("POINT(-77.0365 38.8980)", srid=4326),
                source_artifact_id=artifact_id_2024,
            )
        )

    # Query to verify both vintages coexist and neither was overwritten
    with session() as active_session:
        vintages = active_session.execute(
            select(boundary.c.boundary_vintage, boundary.c.source_artifact_id)
            .where(boundary.c.geography_id == geography_id)
            .order_by(boundary.c.boundary_vintage)
        ).mappings().all()

    assert len(vintages) == 2
    assert vintages[0]["boundary_vintage"] == 2020
    assert vintages[0]["source_artifact_id"] == artifact_id_2020
    assert vintages[1]["boundary_vintage"] == 2024
    assert vintages[1]["source_artifact_id"] == artifact_id_2024


def test_duplicate_tiger_boundary_vintage_rejected(catalog_database: None) -> None:
    """Duplicate boundary vintage for the same geography violates unique constraint."""
    geography_id = _contract_geography("dup-vintage")
    artifact_id = _contract_artifact("tiger-vintage-dup")
    boundary = geography_boundary_table()

    with session() as active_session:
        active_session.execute(
            insert(boundary).values(
                geography_id=geography_id,
                boundary_vintage=2020,
                geom=WKTElement("POINT(-77.0365 38.8977)", srid=4326),
                source_artifact_id=artifact_id,
            )
        )

    # Inserting second boundary with the same geography_id and vintage 2020 must fail
    with pytest.raises(IntegrityError), session() as active_session:
        active_session.execute(
            insert(boundary).values(
                geography_id=geography_id,
                boundary_vintage=2020,
                geom=WKTElement("POINT(-77.0365 38.8999)", srid=4326),
                source_artifact_id=artifact_id,
            )
        )
