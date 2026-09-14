---
title: OpenDiscourse epics and stories
status: final
created: 2026-09-14
updated: 2026-09-14
inputDocuments:
  - planning-artifacts/prds/prd-opendiscourse-2026-09-14/prd.md
  - planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md
  - specs/spec-opendiscourse/SPEC.md
  - specs/spec-opendiscourse/reuse.md
  - specs/spec-opendiscourse/v1-scope.md
---

# OpenDiscourse — epics and stories

Fast-path decomposition. No UX spine (CLI/TUI already exist; no new UI epic).

## Extracted requirements

**FR-1..FR-19** as in the PRD. **NFR:** provenance, capacity fail-closed,
parameterized SQL, pytest+PostGIS, BMAD change-sizing, database name
`opendiscourse`. **Architecture extras:** AD-1..AD-7, FRED as first Connector,
no Playwright-first TEA, OpenStates FDW not a physical merge.

## Epic 1 — Development substrate

*Mostly landed on `main` (BMAD/TEA, CI fast lane, extras, Serena, postgres
skills, upstream bootstrap). Remaining stories still matter.*

### Story 1.1 — AGENTS.md constitution — done
As an agent, I follow a short constitution (hierarchy of truth, reuse-first,
Connector vs inventory, definition of done) instead of a creed-only AGENTS.md.
Acceptance: `bmad-project-context` adopts existing AGENTS.md; CLAUDE.md is a
stub; no GROK.md fork. Landed: managed `<!-- bmad:context -->` block in
`AGENTS.md`; `CLAUDE.md` is `@AGENTS.md`.

### Story 1.2 — ADR-0001 Postgres system of record — done
As an operator, I have ADR-0001 in `docs/adr/` matching AD-1.
Acceptance: file exists; AGENTS.md points at it.
Landed: `docs/adr/0001-postgres-system-of-record.md`; `AGENTS.md` Where things
are lists `docs/adr/`.

### Story 1.3 — OpenDiscourse skills — done
As an agent, I have project skills for connector, schema-change, provenance,
testing.
Acceptance: four skills under `.agents/skills/` (or `_bmad/custom`) with
when-to-use; Grok discovers them.
Landed: `.agents/skills/opendiscourse-{connector,schema-change,provenance,testing}`.

### Story 1.4 — GitHub ruleset (optional solo)
As an operator, `main` requires PR + CI, no force-push, squash; no extra
human approver.
Acceptance: documented; applied if GitHub permissions allow.

## Epic 2 — Connector protocol + FRED reference

### Story 2.1 — Connector Protocol
As a developer, I have a typed Connector interface covering the 10-stage
lifecycle.
Acceptance: Protocol in code; tests for the interface; no schema change.

### Story 2.2 — Registry without HANDLERS if/elif
As a developer, I register FRED without adding to a hardcoded handler set.
Acceptance: FRED path does not need a new `plans.py` elif.

### Story 2.3 — Migrate FRED end-to-end
As an operator, FRED discover/index vs observations still split; observations
still contract-gated.
Acceptance: Existing FRED tests pass; provenance unchanged.

## Epic 3 — Identity crosswalk

### Story 3.1 — Load congress-legislators
As a researcher, BioGuide IDs land in `core.person` / `person_identifier`
from `vendor/congress-legislators`.
Acceptance: Idempotent load; provenance artifact; no name matching.

### Story 3.2 — Gate v1.1 sources
As an operator, FEC/disclosure/crime plans stay disabled until Story 3.1
is green.
Acceptance: Inventory/progress states say identity-blocked.

## Epic 4 — Wrap unitedstates/congress

### Story 4.1 — Senate + House votes producer
As a researcher, both chambers' roll calls ingest via wrapped
`vendor/unitedstates-congress`.
Acceptance: No new scraper module that parses clerk XML directly; checksummed
raw; maps to `core.roll_call` / `fact.member_vote`.

## Epic 5 — Research packs and marts

### Story 5.1 — Pack docs
As a researcher, I have named packs: place-year social, policy/representation,
macro/financial.
Acceptance: Documented in `docs/` and status/browse copy; no new schema.

### Story 5.2 — dbt marts
As a researcher, `district_year` and `legislator_vote` (or equivalent) build
from `core`/`fact`.
Acceptance: dbt tests; mart schema already exists.

## Epic 6 — Access

### Story 6.1 — PostgREST views
As a researcher, reviewed read-only views exist in `api` for v1 spine tables
that are already loaded.
Acceptance: No `ingest`/`stage` exposure; Compose profile still works.

### Story 6.2 — DuckDB/Parquet export
As a researcher, exports do not `fetchall()` unbounded sets.
Acceptance: Streaming/chunked path; analytics extra.

## Epic 7 — v1.1 money, elections, crime

Blocked on Epic 3. Stories TBD after CAP-4. Do not start.

## Coverage

| FR | Epic |
|---|---|
| FR-1..3 | 2, existing ingest |
| FR-4..5 | 2 |
| FR-6 | existing + 4 |
| FR-7 | 4 |
| FR-8..9 | 3 |
| FR-10..12 | existing bulk |
| FR-13 | 5 |
| FR-14..16 | 6 |
| FR-17..19 | 1 |

## Suggested next build

`bmad-build` Story 2.1 (Connector protocol), then 2.2–2.3 (FRED).
