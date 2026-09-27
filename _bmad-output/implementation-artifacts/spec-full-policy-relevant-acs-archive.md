---
title: 'Build full policy-relevant ACS, PUMS, and AHS archive'
type: 'feature'
created: '2026-09-27'
status: 'in-review'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '6a1ca78fc3a4e36c09b02e543ac9f33d1b3acc5e'
context:
  - '_bmad-output/specs/spec-housing-microdata-archive/SPEC.md'
  - '_bmad-output/specs/spec-housing-microdata-archive/product-and-field-policy.md'
  - '_bmad-output/specs/spec-opendiscourse/schema-invariants.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** OpenDiscourse needs complete nationwide, historical public housing and household evidence to study policy effects. Existing ACS code only loads a 2021-2024, five-year, state/county Detailed Table slice and has no PUMS, AHS, annual ACS, product-inventory, or expandable field layer.

**Approach:** Build reusable Census connectors and source contracts that discover, capacity-gate, retain, and resume the complete official public archive: ACS PUMS 1-year/5-year, AHS public-use releases, and ACS Detailed/Summary, Data Profile, Subject, Comparison, Selected Population, Narrative, Supplemental, Ranking, Geographic Comparison, and variance-replicate products. Preserve all raw evidence and dictionaries, then publish an explicitly governed analytic projection covering demographic, income, education, family, housing, and employment values.

## Boundaries & Constraints

**Always:** Keep ACS 1-year and 5-year, PUMS, AHS, and every release/product/component/vintage distinct; acquire bytes only from official endpoints into `DATA_ROOT`; register immutable checksums, field definitions, release metadata, provenance, capacity, and resumable checkpoints; use the 10-stage Connector protocol; retain all raw current-version public files even when a field is not initially promoted; preserve PUMS weights and PUMA geography; select AHS current relational CSVs without treating flat or superseded versions as independent observations; archive nonstandard/experimental releases separately with a visible nonstandard status rather than substituting them for standard estimates.

**Never:** Cut nationwide or historical coverage because of arbitrary field selection; create a false 2000 ACS or 2020 standard 1-year release; represent PUMS as identified household/county microdata; add a `cli.py`, `plans.py`, or registry dispatcher branch; use a generic EAV fact table; treat crime as ACS/AHS data; interrupt the active 2021-2024 ACS 5-year load.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Full release discovery | Official index exposes a current file, dictionary, and release note | One manifest entry per artifact with product, period, component, version, URL, and byte count | Reject incomplete or ambiguous version selection. |
| Publisher gap | 2020 ACS 1-year or AHS 2000 has no public release | Record the gap in the manifest and coverage report | Do not synthesize a dataset or silently omit it. |
| Re-run after interruption | Some bytes/artifacts already retained | Resume verified partial transfer and skip usable current artifacts | Failed newest bytes never shadow verified evidence. |
| Duplicate representations | AHS relational, flat, and superseded packages exist | Retain selected evidence according to manifest; publish only the current relational representation | Reject an attempt to publish duplicate observations. |
| New approved field | Raw source artifact is retained but field is not in initial projection | Parse and publish the mapped field from retained artifact | Do not redownload; reject unregistered/undefined fields. |

</frozen-after-approval>

## Code Map

- `src/opendiscourse_research/ingestion/connector.py` -- required ten-stage Connector protocol and checkpoint semantics.
- `src/opendiscourse_research/ingestion/bulk.py` -- reuse capacity preview, plan state, resumable immutable download, checksum, and artifact locking.
- `src/opendiscourse_research/providers/census.py` -- Census-only official-index discovery; existing bulk package function remains five-year Detailed Table-specific.
- `src/opendiscourse_research/ingestion/acs_bulk.py` and `acs_load.py` -- do not reuse as microdata model; they parse modern table-based estimate cells only.
- `src/opendiscourse_research/repositories/artifacts.py` and `ingestion/base.py` -- mandatory current-artifact and ingest-run provenance boundary.
- `inventory/sources.yaml` and `inventory/contracts/` -- add stable datasets/contracts, never a central dispatch path.
- `migrations/`, `src/opendiscourse_research/models/`, `docs/persistence-migration-status.md` -- Alembic-owned source-shaped microdata schema and durable model documentation.
- `tests/test_connector.py`, `tests/test_census_bulk_integration.py`, and DB fixtures -- patterns for lifecycle, lineage, resume, and idempotency coverage.

## Tasks & Acceptance

**Execution:**
- [ ] `inventory/sources.yaml`, `inventory/contracts/`, and `providers/census.py` -- register and discover all standard ACS product families, PUMS, and AHS releases/components/versions from original publisher indexes; emit a reviewed, exact capacity manifest including publisher gaps.
- [ ] `src/opendiscourse_research/ingestion/` and connector registration boundary -- implement reusable PUMS/AHS/archive connectors using the existing ten stages, retained artifacts, documented file selection, and actionable resume checkpoints.
- [ ] `migrations/`, `models/`, and `repositories/` -- add Alembic-owned, source-shaped stage and bounded typed household/person/unit records plus release/field-definition metadata; preserve artifact/member/ordinal lineage, product/period, PUMA, survey component, and value labels without a generic EAV fact table.
- [ ] `inventory/fields/` and field-policy repository/model -- catalog every official field and map the first policy-domain projection: demographics, income/poverty, education, family, housing value/cost/quality, employment/mobility; document crime as a separate future official source.
- [ ] `tests/`, `docs/`, and an operational refresh command -- prove historical release discovery, 2000/2020 gaps, current-version choice, capacity failure, download resume, artifact provenance, stage/publish idempotency, PUMS geography, AHS component separation, field expansion from retained files, and reproducible full-refresh instructions.

**Acceptance Criteria:**
- Given each official index, when the archive is discovered, then every available release/product/component is manifested with its official documentation and every publisher absence is named.
- Given an approved manifest, when transfer resumes or repeats, then bytes remain immutable, checksummed, provenance-linked, and free of duplicate canonical records.
- Given a retained PUMS/AHS artifact, when an approved policy-domain field is added, then it is published from that artifact without a new download and retains its source definition and value labels.
- Given a PUMS record or AHS component, when it is queried, then its product, period, geography/survey limits, and original artifact are visible and it cannot be misrepresented as county-level identified household data.
- Given the existing ACS five-year loader, when the new connectors are introduced, then its current behavior and active run remain unchanged.

## Implementation Notes

The connector now has an official-directory HTTP adapter, explicit publisher
gaps, a fail-closed capacity manifest, separate transfer approval, immutable
resumable artifact retention, source-shaped ZIP/CSV staging, and an idempotent
bounded policy projection. The standalone refresh command is
`python -m opendiscourse_research.ingestion.acs_archive --indexes <reviewed-indexes.yaml>`;
adding `--approve-transfer` is required after reviewing its preflight.

The checked-in work is deliberately still `in-progress`: it does not yet ship
the reviewed, exhaustive list of every historical ACS/AHS publisher index, nor
does it parse every publisher dictionary/value-label format into the field
catalog. Those are required before any task can be marked complete or a full
nationwide refresh can be claimed.

## Spec Change Log

## Review Triage Log

## Design Notes

Raw completeness and canonical usability are separate layers: complete publisher files and dictionaries are retained as evidence; source-shaped stage retains parser fidelity; bounded typed records and policy-domain projections serve researchers. This makes a future approved field a re-parse/promotion operation, not another national download.

## Verification

**Commands:**
- `just check-fast` -- expected: lint and non-DB tests pass.
- `just check-db` -- expected: schema, connector, provenance, and idempotency tests pass without xdist.
- `uv run research-db census-health` -- expected: existing Census plan health remains valid and new manifest coverage reports exact artifacts/gaps.

Implementation check (2026-09-27): `just check-fast` passed (614 tests) and
`just check-db` passed (383 tests). Focused archive tests passed (16 tests),
including official-directory discovery, legacy publisher layouts, publisher
gaps, capacity failure, missing HEAD byte sizes, transfer approval, AHS CSV
selection, and protocol checkpoint behavior. The live preflight selected 3,762
artifacts with no unknown byte sizes and stopped before transfer as required.
