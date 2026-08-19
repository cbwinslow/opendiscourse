# Persistence migration status

Last verified: 2026-08-19

## Adopted stack

SQLModel/SQLAlchemy is the application persistence API. Alembic owns the
adopted `catalog` schema plus OpenStates evidence tables
`ingest.run`, `ingest.raw_payload`, `ingest.resume_cursor`, and
`ingest.identity_exception`, `ingest.artifact`, and `ingest.cursor`; the
existing ordered `sql/` files remain the schema owner for every other schema
except adopted `core.geography` and `fact.measurement`, until its bounded
migration is explicitly approved. SQLAlchemy continues to use the project's
`psycopg` driver.

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
