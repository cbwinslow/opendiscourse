# Persistence migration status

Last verified: 2026-08-19

## Adopted stack

SQLModel/SQLAlchemy is the application persistence API. Alembic owns the
adopted `catalog` schema plus OpenStates evidence tables
`ingest.run`, `ingest.raw_payload`, `ingest.resume_cursor`, and
`ingest.identity_exception`, `ingest.artifact`, and `ingest.cursor`; the
existing ordered `sql/` files remain the schema owner for every other schema
except adopted `core.geography` and `fact.measurement`, until its bounded
migration is explicitly approved. Alembic also owns the adopted
`core.geography_boundary`, `core.jurisdiction`, and
`core.legislative_session`, `core.bill`, and `core.bill_identifier` tables.
Alembic also owns `core.person` and `core.person_identifier`. SQLAlchemy
continues to use the project's `psycopg` driver. `core.bill_action` is also
Alembic-adopted, as is `core.bill_sponsorship`.
`core.bill_committee` and `core.bill_subject` are also Alembic-adopted.
`core.document` and `core.bill_document` are also Alembic-adopted.
`core.organization` and `core.organization_identifier` are also
Alembic-adopted.
`core.roll_call` and `fact.member_vote` are also Alembic-adopted.

The Alembic baseline and adoption revisions are markers over the legacy-seeded
schemas. The real PostGIS regression suite verifies both downgrade to `base`
and re-upgrade to the adopted revision without changing legacy tables.

## Completed typed boundaries

- Alembic-owned catalog models and browser/repository/registry persistence:
  providers, datasets, fields, resources, baskets, snapshots, plans, and
  discovery leases.
- Alembic-adopted immutable ingestion evidence: runs, raw payloads, resume
  checkpoints, unresolved identity exceptions, and local artifacts, including
  their validation constraints and lookup indexes.
- Alembic-adopted shared ingestion plan cursor, including its run-success
  lineage foreign key.
- Alembic-adopted shared canonical primitives: geography and measurements,
  including the measurement lookup index and NULLS-NOT-DISTINCT identity key.
- Alembic-adopted PostGIS geography boundaries, including source evidence
  lineage and the legacy-named GiST geometry index.
- Alembic-adopted legislative dimensions: jurisdictions and source-evidenced
  legislative sessions.
- Alembic-adopted canonical bill identity and identifiers, including source
  evidence, reverse identifier lookup, and partial OCD-ID uniqueness.
- Alembic-adopted canonical people and their stable external identifiers.
- Alembic-adopted canonical bill actions, including their source-evidence
  check and partial source-member idempotency index.
- Alembic-adopted bill sponsorships, including role validation, source
  evidence, NULLS-NOT-DISTINCT identity, and person linkage indexing.
- Alembic-adopted bill committees and subjects, each with source evidence and
  NULLS-NOT-DISTINCT source-member identity.
- Alembic-adopted canonical documents and their legacy bill-link relationship.
- Alembic-adopted canonical organizations and stable organization identifiers.
- Alembic-adopted roll calls and member votes, including partial OCD-ID
  uniqueness and artifact-or-payload vote provenance.
- Catalog search extensions and actual plan usage: `pg_trgm`, `unaccent`,
  trigram title search, and full-text GIN search.
- Immutable ingestion evidence: artifacts, runs, raw payloads, and plan
  cursors, including OpenStates resume checkpoints and unresolved voter
  identity exceptions.
- API observations: ACS, FRED, and BLS now upsert canonical measurements
  through typed SQLAlchemy contracts with raw-payload provenance.
- Canonical geography, measurements, and PostGIS geography boundaries have
  typed external contracts. GeoAlchemy2 geometry/SRID behavior is exercised
  against PostGIS.
- Artifact resolution in ACS, CBP, DHC, PEP, TIGER, and FEC bulk loaders is
  typed and status-filtered.
- Connection-free GovInfo BILLSTATUS graph writes use typed canonical bill,
  identifier, action, sponsorship, committee, subject, and document mappings.
  Supplied caller connections retain the existing atomic raw graph path.
- Congressional unresolved-identity reporting uses typed canonical sponsorship,
  person-identifier, and ingestion-exception mappings.
- Congressional health reporting uses typed bill, person, organization,
  roll-call, member-vote, exception, and run mappings.
- Congress.gov bill API ingestion upserts canonical bills through SQLAlchemy
  with its existing per-page transaction boundary.
- Congress.gov member upserts and connection-free sponsorship resolution use
  typed person, identifier, and sponsorship mappings.
- Treasury yield-curve ingestion upserts canonical measurements through the
  shared typed measurement mapping while preserving per-date commits.

Every migrated database behavior has real PostgreSQL/PostGIS coverage in
`tests/test_persistence_foundation.py`; ORM behavior is not mocked there.

## Deliberately retained psycopg boundaries

These remain raw SQL because they are set-based or provider/staging-specific,
not because their evidence boundary is unmapped:

- Bulk staging `executemany`/COPY and set-based canonical promotions in ACS,
  CBP, DHC, PEP, TIGER, and FEC loaders.
- The OpenStates FDW and its source-schema reconciliation queries.
- Legislative graph writes and provenance reconciliation that operate on the
  OpenStates FDW or require a supplied caller transaction.
- Dynamic fact-table health counts, where table names are selected from the
  reviewed health family map.

Future migrations must keep artifact/raw-payload lineage, idempotent conflict
keys, batch/commit semantics, and the source-owned staging shape intact. A
loader may use psycopg for COPY or a complex `INSERT … SELECT` while using the
typed contracts for reusable persistence and evidence lookup.
