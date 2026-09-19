# Related schema files already in this repository

The live dump in this directory is the as-built warehouse. These
paths are the owned contracts and runtime SQL ChatGPT should read
alongside it. Do not treat `sql/NNN_*.sql` as a second migration
path.

## Bootstrap SQL (legacy reference, not a second migration path)

- `sql/001_extensions.sql`
- `sql/002_core.sql`
- `sql/003_facts.sql`
- `sql/004_bulk_artifacts.sql`
- `sql/005_ops.sql`
- `sql/006_docvec.sql`
- `sql/007_plan_mode.sql`
- `sql/008_catalog_browser.sql`
- `sql/009_catalog_snapshots.sql`
- `sql/010_catalog_discovery.sql`
- `sql/011_legislative_reconciliation.sql`
- `sql/012_openstates_baseline.sql`
- `sql/013_openstates_compatibility_views.sql`
- `sql/014_organization_identifiers.sql`
- `sql/015_vote_artifact_provenance.sql`
- `sql/016_census_bulk.sql`
- `sql/017_population_estimates.sql`
- `sql/018_tiger_bulk.sql`
- `sql/019_dhc_bulk.sql`
- `sql/020_openstates_vote_resume.sql`
- `sql/021_vote_identity_exceptions.sql`
- `sql/022_acs_bulk.sql`
- `sql/023_mart_schema.sql`
- `sql/024_fec_bulk.sql`
- `sql/025_search_extensions.sql`

## Runtime SQL

- `sql/query/access/ensure_api_schema.sql`
- `sql/query/catalog/claim_discovery.sql`
- `sql/query/catalog/delete_resources_prefix.sql`
- `sql/query/catalog/get_discovery.sql`
- `sql/query/catalog/resource_ids.sql`
- `sql/query/catalog/upsert_discovery.sql`
- `sql/query/catalog/upsert_fred_search.sql`
- `sql/query/catalog/upsert_resource.sql`
- `sql/query/legislation/bill_keys.sql`
- `sql/query/legislation/canonical_vote_counts.sql`
- `sql/query/legislation/congress_health.sql`
- `sql/query/legislation/ensure_jurisdiction.sql`
- `sql/query/legislation/ensure_legislative_session.sql`
- `sql/query/legislation/fail_stale_runs.sql`
- `sql/query/legislation/find_bill_by_ocd.sql`
- `sql/query/legislation/find_organization_by_identifier.sql`
- `sql/query/legislation/find_person_by_identifier.sql`
- `sql/query/legislation/get_artifact.sql`
- `sql/query/legislation/get_resume_cursor.sql`
- `sql/query/legislation/loaded_artifact_members.sql`
- `sql/query/legislation/openstates_federal_organizations.sql`
- `sql/query/legislation/openstates_federal_people.sql`
- `sql/query/legislation/openstates_person_identifiers.sql`
- `sql/query/legislation/openstates_person_vote_snapshot_count.sql`
- `sql/query/legislation/openstates_person_votes.sql`
- `sql/query/legislation/openstates_vote_events.sql`
- `sql/query/legislation/openstates_vote_snapshot_counts.sql`
- `sql/query/legislation/publish_openstates_compatibility_views.sql`
- `sql/query/legislation/record_vote_identity_exception.sql`
- `sql/query/legislation/register_artifact.sql`
- `sql/query/legislation/resolve_bill_sponsorship_people.sql`
- `sql/query/legislation/save_resume_cursor.sql`
- `sql/query/legislation/unresolved_identity_exceptions.sql`
- `sql/query/legislation/upsert_bill.sql`
- `sql/query/legislation/upsert_bill_action.sql`
- `sql/query/legislation/upsert_bill_committee.sql`
- `sql/query/legislation/upsert_bill_document.sql`
- `sql/query/legislation/upsert_bill_identifier.sql`
- `sql/query/legislation/upsert_bill_sponsorship.sql`
- `sql/query/legislation/upsert_bill_subject.sql`
- `sql/query/legislation/upsert_document.sql`
- `sql/query/legislation/upsert_member_vote.sql`
- `sql/query/legislation/upsert_openstates_roll_call.sql`
- `sql/query/legislation/upsert_organization_by_ocd.sql`
- `sql/query/people/find_identifier_owners.sql`, `attach_person_identifiers.sql`, `merge_*.sql` (ADR-0005 identity)

## Alembic revisions

- `migrations/versions/a2e6c4d9f187_adopt_canonical_organizations.py`
- `migrations/versions/a5d9e2c7f418_adopt_canonical_bill_identity.py`
- `migrations/versions/a8d5e2c7f361_adopt_document_retrieval_support.py`
- `migrations/versions/a9e4c1b78f20_adopt_ingest_run_evidence.py`
- `migrations/versions/b3f1d8e6c492_adopt_core_geography_and_measurements.py`
- `migrations/versions/b4e8c1d7a593_adopt_population_estimates.py`
- `migrations/versions/b6c3e8a1d574_adopt_bill_sponsorships.py`
- `migrations/versions/b9e3a6d4f182_adopt_canonical_memberships.py`
- `migrations/versions/c2d7e4a9b631_adopt_ingest_artifacts.py`
- `migrations/versions/c4f7a2d9e651_adopt_bulk_staging_tables.py`
- `migrations/versions/c5a7e2d8b419_adopt_business_patterns.py`
- `migrations/versions/c8f4a1d6e257_adopt_canonical_people.py`
- `migrations/versions/d207df35ca10_baseline_catalog_schema.py`
- `migrations/versions/d3f6a8c1e274_adopt_acs_bulk_estimates.py`
- `migrations/versions/d4e6a1b9c573_adopt_legislative_dimensions.py`
- `migrations/versions/d7a4e1c9b265_adopt_canonical_documents.py`
- `migrations/versions/e1b5d7a9c364_adopt_bill_actions.py`
- `migrations/versions/e4c2a9d6b731_adopt_decennial_dhc_values.py`
- `migrations/versions/e6c9d2f41a85_adopt_ingest_plan_cursor.py`
- `migrations/versions/e8b1c5d4a296_adopt_roll_calls_and_member_votes.py`
- `migrations/versions/f1c7e3a9d582_adopt_financial_primitives.py`
- `migrations/versions/f5e8a3c47d12_adopt_ingest_evidence.py`
- `migrations/versions/f7a2c8d5e139_adopt_postgis_geography_boundaries.py`
- `migrations/versions/f9d2a6c4e183_adopt_bill_committees_and_subjects.py`

## Alembic baseline DDL

- `migrations/baseline/d207df35ca10.sql`

## SQLModel contracts

- `src/opendiscourse_research/models/__init__.py`
- `src/opendiscourse_research/models/catalog.py`
- `src/opendiscourse_research/models/core.py`
- `src/opendiscourse_research/models/ingest.py`
- `src/opendiscourse_research/models/stage.py`

## SQL repositories

- `src/opendiscourse_research/repositories/__init__.py`
- `src/opendiscourse_research/repositories/catalog.py`
- `src/opendiscourse_research/repositories/legislation.py`

## dbt models

- `dbt/models/marts/mart_geography_year_measurement.sql`
- `dbt/models/marts/mart_roll_call_results.sql`
- `dbt/models/staging/stg_bills.sql`
- `dbt/models/staging/stg_geography.sql`
- `dbt/models/staging/stg_measurements.sql`
- `dbt/models/staging/stg_member_votes.sql`
- `dbt/models/staging/stg_roll_calls.sql`

## dbt model YAML

- `dbt/models/marts/_marts.yml`
- `dbt/models/staging/_sources.yml`
- `dbt/models/staging/_staging.yml`

## Inventory and contracts

- `inventory/acs_housing_groups.yaml`
- `inventory/contracts/acscomprehensive.yaml`
- `inventory/contracts/acshousing.yaml`
- `inventory/contracts/billstatus.yaml`
- `inventory/contracts/census.yaml`
- `inventory/contracts/congressional_refresh.yaml`
- `inventory/contracts/fecbulk.yaml`
- `inventory/core_bls_series.yaml`
- `inventory/core_fred_series.yaml`
- `inventory/plans.yaml`
- `inventory/progress.yaml`
- `inventory/sources.yaml`

## Ops scripts

- `ops/census-bulk-refresh.sh`
- `ops/systemd/opendiscourse-census-health.service`
- `ops/systemd/opendiscourse-census-health.timer`
- `ops/systemd/opendiscourse-census-metadata.service`
- `ops/systemd/opendiscourse-census-metadata.timer`
- `ops/systemd/opendiscourse-fred.service`
- `ops/systemd/opendiscourse-fred.timer`

## Project scripts

- `scripts/bootstrap_upstream.sh`
- `scripts/export_schema_snapshot.py`
- `scripts/render_baseline_ddl.py`

## Product and architecture (review order)

- `AGENTS.md`
- `_bmad-output/specs/spec-opendiscourse/SPEC.md`
- `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`
- `_bmad-output/planning-artifacts/epics.md`
- `docs/adr/0001-postgres-system-of-record.md`
- `docs/model.md`
- `docs/openstates-integration.md`
- `docs/persistence-migration-status.md`
- `docs/runtime.md`
- `docs/schema-snapshot/spec-8-1-post-division-membership.md`

Prior ChatGPT essays in `docs/research/` are research, not the
current epic list.
