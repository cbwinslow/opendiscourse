# Blueprint

## Decision

Use a lakehouse-shaped system, not a single ever-growing Postgres database.
Postgres/PostGIS is the durable research catalog and curated query layer.
Immutable original files live in object storage (local `data/` during
development, S3-compatible storage in production).  This preserves the
evidence behind every result while preventing large, rarely queried source
archives from consuming the primary database.

```
provider -> fetch -> raw object -> parse -> typed tables -> research views
              |          |              |              |
             plan     artifact        run          document/embed
```

The one-word, short operator names are deliberate: `fredcore`, `acshome`, and
`congcur` are runnable plans.  Provider and dataset IDs retain dots because
they are stable, externally meaningful catalog paths (`census.acs_5`), not
human command names.

## Layers

| Layer | Role | Stored here |
|---|---|---|
| raw | Immutable original evidence | object storage; URL, checksum, and coverage in `ingest.artifact` |
| log | Reproducible operation history | `ingest.run`, `ingest.raw_payload`, `ingest.cursor` |
| core | Cross-source identities | geography, people, organizations, bills, documents |
| fact | Narrow analytical observations | measurements, votes, awards, crime, election results |
| mart | Purpose-built research views | bill timelines, member records, place-year panels, impact cohorts |

Do not use an all-purpose JSON facts table. Keep source-specific parser output
in staging or raw objects, then load stable analytical grains into typed tables.
`fact.measurement` remains appropriate for modest scalar series such as
FRED/BLS. High-volume ACS Detailed Tables use the ADR-0006 packed
release × geography × table grain; bills, documents, votes, sponsors, money,
and GIS each keep their own typed grain.

## Contracts and refresh

`inventory/sources.yaml` says what a source is. `inventory/plans.yaml` says
exactly what the system is allowed to ingest: source, handler, cadence, and
parameters. A plan is reviewed in Git before it can run. The CLI runs a plan
or all due plans; a scheduler should invoke `research-db plan-due` daily.

Each new adapter must have: a catalog entry, a short plan, raw artifact or
payload capture, an idempotent parser, a typed target grain, and a cursor or
other refresh rule. It must not silently expand a source's scope.

## Legislative path

1. Bootstrap Congress.gov bill metadata one Congress at a time with bounded
   pages; retain its raw responses and use it for frequent updates.
2. Acquire GovInfo BILLSTATUS and bill-text bulk artifacts into raw storage;
   parse package/version IDs and link the resulting canonical text documents
   to the existing Congress bill identity.
3. Add people, memberships, sponsors, actions, committees, roll calls, and
   votes as separate typed grains. Reconcile by Bioguide ID, never name alone.
4. Chunk each retained text deterministically. Generate model-versioned
   embeddings from chunks. An embedding augments, never replaces, source text.
5. Build explicit policy studies as marts: define a bill's treatment date,
   affected places/industries, outcome windows, and confounders before running
   any model.

## Initial delivery order

BMAD `v1-scope.md` wins. FBI/crime remain v1.1. FEC is a separately approved,
strict-gated programme; planning is authorized, but transfer, promotion, and
politician joins still require their own completion evidence.

1. Make the current schema and plans runnable in a local Postgres container.
2. Identity crosswalk (BioGuide) and legislative primitives (Epic 8), then
   wrap Congress.gov / GovInfo / clerk votes into `core` (not the OpenStates
   dump).
3. Epic 10 proves one jurisdiction-time vertical slice in strict order:
   119th CD + 2024 SLD TIGER boundaries → division/boundary link → packed
   2024 ACS congressional-district facts → metric registry →
   `mart.congressional_district_period`. Do not start national block/tract
   expansion or horizontal topic sources before that slice passes.
4. After `slice_proven`, add CVAP, CBP congressional-district, IRS SOI,
   LODES, USAspending and later topic sources one verified Connector at a time;
   keep `legislator_vote` and reviewed access views/exports as separate marts.
5. **Post-v1:** disclosures, elections, crime/FBI. The FEC/OpenStates
   programme follows its own gates: field/coverage mapping, pilot, typed model,
   approved 2000–2024 batches, identifier bridge, then marts. Existing
   `stage.fec_row` is not authorization.

Document chunking / pgvector column promotion remains a later ADR. For
production embeddings, use a Postgres image with both PostGIS and pgvector
or keep vectors in a dedicated compatible Postgres service. The portable
base schema stores dimension-checked arrays so source-document ingestion is
not blocked by that deployment decision.
