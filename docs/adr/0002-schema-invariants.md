# ADR-0002: Schema invariants

- Status: Accepted
- Date: 2026-09-17
- Spine: AD-10 in `_bmad-output/planning-artifacts/architecture/architecture-opendiscourse-2026-09-14/ARCHITECTURE-SPINE.md`
- Detail: `_bmad-output/specs/spec-opendiscourse/schema-invariants.md`

## Context

The 2026-09-17 schema review (archived at
`docs/research/2026-09-17-chatgpt-schema-review.md`) validated the current
warehouse against the BMAD spec, architecture spine, PRD, and live snapshot
in `docs/schema-snapshot/`. The architecture is keep-and-refine, not a
redesign. Remaining risk is inconsistency: dual legislative identity
columns, provenance CHECKs that are not universal, and docs that still
imply v1 crime or market ingest.

## Decision

1. **Internal UUID primary keys.** External identifiers (BioGuide, OCD,
   congress+type+number, official roll-call id) live in identifier tables or
   dedicated unique columns. They are not physical primary keys.
2. **No name-based entity reconciliation.** Federal person joins use
   BioGuide (CAP-4). OCD IDs are preserved. Display names are labels.
3. **Provenance for source-derived rows.** A source-derived `core`/`fact`
   row must carry direct evidence (`source_artifact_id` or
   `source_payload_id`). Derived rows need derivation lineage. Reference
   or system-generated rows are documented exceptions (see companion).
4. **Schema support is not authorized ingest.** A `stage` table or retained
   market primitive does not open Epic 7 or stock-bar ingestion.
5. **Typed grains.** Do not collapse bills, votes, GIS, ACS, or money into
   one generic JSON facts table. `fact.measurement` is for scalar
   dataset/field/geography/period series.
6. **Ownership.** Alembic owns `catalog` / `core` / `fact` / `ingest` /
   `stage`. dbt owns `mart`. Epic 6 owns published `api` views. `leg` is
   FDW/compatibility, not a second canonical warehouse.
7. **Transitional legislative identity.** `core.bill.jurisdiction`,
   `core.bill.legislative_session`, and the same text columns on
   `core.roll_call` are compatibility columns. Canonical session is
   `legislative_session_id`. Do not build new logic that treats the text
   pair as a second identity. Do not drop the columns until unique keys
   and loaders move to the FK (later story).
8. **Vintage geography.** Never overwrite historical TIGER boundaries.
   `parent_geoid` stays a loose string in v1; `core.geography_relationship`
   is deferred.

## Alternatives considered

| Option | Why not |
|---|---|
| Redesign toward generic entity/attribute/value | Rejected by the review; typed grains are the useful middle |
| Copy OpenStates Django schema into `opendiscourse` | AD-8; dump stays replace-only FDW |
| Rip `core.instrument` / `fact.market_bar` now | Empty compatibility tables; later disclosures may need an instrument id without market bars |
| Require evidence on every `core.person` / `core.geography` row immediately | Identity/reference rows often exist before a specific ingest; classify then enforce, do not blanket-CHECK overnight |
| Drop textual session columns in this change | Unique keys and `sql/query/legislation/upsert_bill.sql` still use them |

## Consequences

- New Alembic work follows the companion classification, not ad-hoc CHECKs.
- Story 8.1 may add `core.post` / `core.division` with the same
  artifact-or-payload evidence rule used by membership.
- Provenance-gap tests (source-less vote/membership rejected, duplicate
  external person id rejected) are a follow-on story, not this ADR.
- Blueprint, PRD persona, and persistence status must match this file;
  ChatGPT essays do not.
