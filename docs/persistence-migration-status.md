# Persistence migration status

Last verified: 2026-08-19

## Adopted stack

SQLModel/SQLAlchemy is the application persistence API. Alembic owns all
application table contracts in the `catalog`, `core`, `fact`, `ingest`,
and `stage` schemas. Alembic creates a new database with the frozen,
reviewable DDL artifact at `migrations/baseline/d207df35ca10.sql`; the ordered
`sql/` files remain as legacy-history references while adoption revisions
preserve a reversible upgrade history. Alembic also owns the adopted
`core.geography_boundary`,
`core.jurisdiction`, and
`core.legislative_session`, `core.bill`, and `core.bill_identifier` tables.
Alembic also owns `core.person` and `core.person_identifier`. SQLAlchemy
continues to use the project's `psycopg` driver. `core.bill_action` is also
Alembic-adopted, as is `core.bill_sponsorship`.
`core.bill_committee` and `core.bill_subject` are also Alembic-adopted.
`core.document` and `core.bill_document` are also Alembic-adopted.
`core.organization` and `core.organization_identifier` are also
Alembic-adopted.
`core.membership` is also Alembic-adopted.
`core.document_chunk` and `core.embedding` are also Alembic-adopted.
`core.roll_call` and `fact.member_vote` are also Alembic-adopted.
`fact.population_estimate` is also Alembic-adopted.
`fact.business_pattern` is also Alembic-adopted.
`fact.acs_bulk_estimate` is also Alembic-adopted.
`fact.decennial_dhc_value` is also Alembic-adopted.
`core.instrument`, `core.instrument_symbol`, and `fact.market_bar` are also
Alembic-adopted.

The baseline creates new schemas directly from static DDL. For a pre-Alembic
database, it preserves the legacy-seeded tables and indexes and records the
adoption history. The real PostGIS regression suite verifies both that safe
adoption and downgrade to `base` followed by re-upgrade without changing
legacy tables.

Run `python scripts/render_baseline_ddl.py --check` to verify that the
reviewed baseline artifact retains its expected normalized fingerprint.

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
- Alembic-adopted memberships, including person, organization, session, and
  artifact-or-payload evidence linkage.
- Alembic-adopted roll calls and member votes, including partial OCD-ID
  uniqueness and artifact-or-payload vote provenance.
- Alembic-adopted PEP population estimates, including source artifact/member
  lineage and the release/year/geography lookup index.
- Alembic-adopted CBP business patterns, including immutable source-row lineage
  and release/year/geography/NAICS lookup.
- Alembic-adopted ACS bulk estimates, including measure validation, immutable
  artifact-row identity, and release/geography/table/field lookup.
- Alembic-adopted decennial DHC values, including immutable artifact/member
  provenance and release/geography/table/variable lookup.
- Alembic-adopted financial instruments, symbols, and provenance-backed market
  bars.
- Alembic-adopted document chunks and portable embeddings, including ordinal,
  dimension, and vector-cardinality integrity checks.
- Alembic-adopted ACS, CBP, DHC, PEP, TIGER, and FEC staging table contracts,
  including their artifact identity keys and legacy lookup/geometry indexes.
- Real PostgreSQL/PostGIS regressions cover retained COPY/executemany staging
  and set-based promotion paths: ACS, CBP, DHC, PEP, TIGER, and FEC
  source-ordinal idempotency run in the standard suite. The caller-supplied
  BILLSTATUS graph transaction and OpenStates compatibility-view publisher are
  also exercised against PostgreSQL; the view test uses an isolated
  source-schema stand-in, never a provisioned FDW snapshot.
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
- The explicit OpenStates compatibility-view publisher, which runs only after
  an externally approved FDW remap and reads its named operational SQL resource.
- Legislative graph writes and provenance reconciliation that operate on the
  OpenStates FDW or require a supplied caller transaction.

The only direct psycopg connection modules are `openstatesrefresh`,
`openstatesstage`, `peopleload`, and `votereconcile` for OpenStates FDW work;
the ACS, CBP, DHC, FEC, PEP, and TIGER loaders for bulk staging/promotion; and
`db` for the shared connection factory. Ordinary browser, catalog, evidence,
health, and connection-free legislative paths use SQLAlchemy sessions and
mapped tables.

Future migrations must keep artifact/raw-payload lineage, idempotent conflict
keys, batch/commit semantics, and the source-owned staging shape intact. A
loader may use psycopg for COPY or a complex `INSERT … SELECT` while using the
typed contracts for reusable persistence and evidence lookup.
