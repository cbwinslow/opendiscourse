> **Research, not the current plan.** Selected decisions were absorbed into
> `_bmad-output/` on 2026-09-17 (AD-8/AD-9, CAP-8, Epic 8). Do not treat this
> essay as a replacement epic list or implement the strangler reboot from it.
> Current contract: `SPEC.md`, architecture spine, `epics.md`.

# OpenDiscourse Comprehensive Architecture & Data Platform Re-Review

**Date:** 2026-09-15
**Repository reviewed:** `cbwinslow/opendiscourse`
**Review posture:** fresh, objective, brownfield re-evaluation. Existing project rules and prior architectural decisions were treated as hypotheses rather than constraints.

---

# Executive verdict

OpenDiscourse is **not a waste of time**, and I do **not** recommend throwing away the repository or starting a completely unrelated repository from zero.

However, I also do **not** recommend simply continuing down the current BMAD epic list unchanged.

The best path is a **controlled internal v2 / strangler-style reboot inside the existing repository**:

1. Preserve the working data lake, provenance machinery, migrations, operational inventory, successful Census/FRED/Treasury/OpenStates/FEC work, tests, Git history, and validated loaders.
2. Freeze new architectural expansion for a short period.
3. Redesign the parts that are still structurally weak **before** loading much more legislative, identity, campaign-finance, disclosure, or cross-domain data.
4. Introduce the improved architecture beside the current implementation.
5. Migrate one source/domain at a time using reconciliation and parity tests.
6. Delete or archive old paths only after the new path has demonstrated equivalent or better behavior.

This gives most of the benefit of “starting over” without throwing away the hardest and most expensive work already completed.

The central product definition should remain:

> **OpenDiscourse is a self-hostable, provenance-aware public-policy and social-science research warehouse that combines authoritative public datasets across identities, geography, time, legislation, government activity, elections, economics, and documents.**

Its value does **not** come from having yet another Census downloader or Congress API wrapper. Its value comes from:

- retaining authoritative source evidence,
- normalizing incompatible sources,
- linking identities and geography over time,
- exposing reproducible research-ready marts,
- making difficult public datasets easy to bootstrap and refresh,
- and letting researchers join questions that normally require several unrelated systems.

---

# Simple summary

In plain terms:

**Do not delete the project and start over from nothing.**

There is too much good work already here. The repo has hundreds of millions of useful Census facts, a complete OpenStates database snapshot, TIGER boundaries, population data, business data, FRED/Treasury data, FEC bulk work, provenance infrastructure, migrations, tests, BMAD, TEA, Serena, and working ingestion tooling.

But some of the architecture should be corrected **now**.

The biggest corrections are:

1. **Fix the government/legislative data model before loading a lot more data.**
   The current model is close to OpenStates/Open Civic Data, but it is missing the important concept of a **post/seat/office**. A legislator does not simply belong to “the House.” They occupy a seat representing a district during a time period. We need that modeled correctly.

2. **Make OpenStates a source, not part of our public schema.**
   Restoring the official PostgreSQL dump separately is a good idea. Using FDW internally is also fine. But OpenStates explicitly says its dump schema is unsupported and may change. Our researchers should query our stable normalized schema, not OpenStates internal Django tables.

3. **Use bulk data for history and APIs for fresh changes.**
   This is the right general rule:
   - bulk dump/archive = historical bootstrap,
   - API/feed = incremental refresh,
   - raw evidence = immutable,
   - our canonical transform = stable research model.

4. **For federal legislation, combine sources instead of choosing one.**
   - GovInfo BILLSTATUS/BILLS/BILLSUM for official bulk legislation and documents.
   - Congress.gov API for current metadata, incremental updates, members, committees, hearings, nominations, treaties, etc.
   - Official House and Senate XML for roll-call votes.
   - `unitedstates/congress` as an established downloader/parser that we can wrap rather than rewriting vote scrapers.
   - `unitedstates/congress-legislators` for historical members and identifier crosswalks.

5. **Simplify the Connector abstraction.**
   The current 10-stage `ConnectorContext -> ConnectorContext` protocol is more ceremony than type safety. Evidence/checkpoints should be handled by the runtime, not forced as provider methods.

6. **Use PostgreSQL features more aggressively instead of writing Python around them.**
   COPY, PostGIS, pg_trgm, real pgvector vectors, BRIN indexes, range types/exclusion constraints, and pg_stat_statements can eliminate custom machinery and improve correctness/performance.

7. **Move market/security data out of OpenDiscourse.**
   `instrument`, `instrument_symbol`, and `market_bar` belong in `cfa-knowledge-base`. Public macroeconomic data such as FRED/BLS/BEA/Treasury still belongs in OpenDiscourse.

8. **Keep BMAD, but reset the BMAD plan.**
   BMAD is a good fit. The current PRD/epics should become historical planning context, and a new architecture-reset change/project should supersede parts of them.

9. **Make CI selective.**
   Unit/parser tests should be extremely fast. Database integration tests should run only for affected changes on PRs, while the full suite runs on main/nightly.

10. **Do not chase a “perfect universal schema.”**
    There is no final schema that can perfectly normalize every government source forever. The correct architecture preserves raw source truth and lets the canonical model evolve safely.

---

# 1. What already exists and is worth preserving

The current repository is much more substantial than a prototype.

According to the project’s current operational inventory, it already contains or manages approximately:

- ~277.7 million ACS facts for 2021–2024 in the existing comprehensive load,
- ~30.6 million County Business Patterns rows,
- ~98.8 million rows in the separately restored OpenStates snapshot,
- ~376k TIGER boundary rows across multiple vintages/layers,
- ~55k Population Estimates rows,
- ~242k FRED observations,
- ~75k Treasury yield observations,
- ~22k Decennial DHC values,
- ~19.7 GB of FEC bulk archives under review/staging,
- several GiB of GovInfo/Congress source artifacts,
- a real catalog/inventory/contract system,
- immutable payload/artifact evidence,
- Alembic migrations,
- PostGIS,
- dbt,
- DuckDB/Parquet support,
- BMAD + TEA,
- Serena,
- project-specific agent skills,
- Ruff/pytest/Hypothesis/testcontainers/xDist,
- a fast CI lane,
- and a typed Connector experiment.

Throwing that away would create a large amount of unnecessary rework.

## Assets to definitely retain

### Data and evidence

Retain:

- all verified immutable source artifacts,
- checksums,
- raw API payloads,
- source URLs,
- timestamps,
- load manifests,
- inventory/contracts,
- coverage reports,
- and progress metadata.

Those are extremely difficult to reconstruct later and are the foundation of reproducible research.

### Strong source pipelines

The existing bulk Census work is one of the strongest parts of the repository.

The following patterns are fundamentally sound:

- ACS Summary File bulk acquisition,
- TIGER/Line vintage-aware boundaries,
- PEP release-vintage separation,
- CBP annual bulk files,
- Decennial bulk ingestion,
- FRED observations with real-time/vintage concepts,
- Treasury official feeds,
- FEC bulk archives,
- monthly OpenStates PostgreSQL snapshots.

These should be **refactored only when there is a concrete architectural benefit**, not rewritten for style.

### Catalog + evidence concepts

The following concepts are valuable and should survive the redesign:

- dataset registry,
- discovered provider resources,
- reviewed selections,
- ingestion plans,
- immutable catalog snapshots,
- ingestion runs,
- raw API payloads,
- bulk artifacts,
- checksums,
- capacity planning,
- resumability,
- source provenance,
- validation before canonical promotion.

The implementation may be simplified, but the concepts are excellent.

---

# 2. What should not be treated as settled

Several current decisions are useful experiments but should not be treated as permanent.

## Current 10-stage Connector protocol

Current stages:

1. discover
2. select
3. plan
4. extract
5. evidence
6. stage
7. normalize
8. validate
9. publish
10. checkpoint

All ten mutate and return the same broad `ConnectorContext`.

That is not as strongly typed as it appears.

The context contains generic dictionaries and extras, and every provider is required to pretend it naturally has the same ten methods.

### Problem

Several stages are not actually provider behavior.

For example:

- `select` is product/catalog behavior.
- `evidence` is a runtime/provenance concern.
- `publish` is a warehouse transaction/promotion concern.
- `checkpoint` is orchestration/runtime state.
- `validate` may have source validation, staging validation, and canonical validation as separate concerns.

A provider should not need to implement placeholder methods for all of these.

### Recommended replacement

Use a smaller typed dataflow plus optional capabilities.

Core flow:

```text
plan
  ↓
acquire
  ↓
stage
  ↓
normalize
  ↓
validate
```

Cross-cutting runtime services handle:

```text
run state
artifact evidence
raw payload evidence
checksums
capacity limits
retry policy
checkpointing
transaction/publish
telemetry
```

Useful typed values:

```python
DatasetSpec
DiscoveryResult
Selection
IngestionPlan
ArtifactRef
PayloadRef
AcquisitionResult
StageResult
NormalizeResult
ValidationReport
Checkpoint
```

Optional protocols/capabilities:

```python
CatalogSource
SnapshotSource
IncrementalSource
StreamSource
Stager
Normalizer
HealthCheck
```

A bulk ZIP source and a paginated REST API should not be forced to look identical internally.

The registry composes capabilities and runtime behavior.

---

# 3. Restart vs refactor vs hybrid

## Option A — continue refactoring the current architecture in place

### Benefits

- lowest immediate cost,
- preserves compatibility,
- no duplicate implementation,
- simplest migration history.

### Problems

- legacy top-level modules are already large,
- architectural experiments become harder to unwind,
- current schema choices constrain new code,
- agents tend to imitate nearby legacy patterns.

This is acceptable for incremental cleanup, but weaker for the amount of redesign now needed.

---

## Option B — brand-new repository

### Benefits

- psychological clean slate,
- clean package boundaries,
- no compatibility pressure,
- no accidental imitation of old modules.

### Problems

- loses Git history/context,
- duplicates working ingestion logic,
- must rebuild migration/bootstrap operations,
- creates data migration problems,
- makes comparison harder,
- encourages rewriting code that already works,
- creates two repositories that may both remain partially alive.

**I do not recommend this.**

---

## Option C — internal v2 / strangler migration in the same repository

### Benefits

- clean architecture can be introduced deliberately,
- existing implementation becomes a test oracle,
- source-by-source parity can be measured,
- working data does not need to be discarded,
- Git history remains intact,
- bad legacy code can be deleted once replaced,
- BMAD can manage the migration as a finite program of work.

### Recommendation

**Choose Option C.**

If a stronger clean-slate feeling is desirable, create a long-lived architecture migration branch and new subpackages inside the existing namespace, but do not fork the product into a disconnected repository.

---

# 4. Revised product boundary

OpenDiscourse should own **public policy / social science / government research data**.

## In scope

### Government and legislation

- federal and state jurisdictions,
- legislative sessions,
- people,
- organizations,
- posts/seats/offices,
- memberships,
- bills/resolutions,
- actions,
- amendments,
- sponsorships,
- committees,
- roll-call votes,
- member votes,
- hearings,
- committee meetings,
- committee reports/prints,
- nominations,
- treaties,
- Congressional Record,
- statutes,
- government documents.

### Geography and demography

- Census geographies,
- TIGER boundaries,
- ACS,
- Decennial Census,
- PEP,
- CBP,
- selected Census government/business programs.

### Economics/public finance

- FRED/ALFRED,
- BLS,
- BEA,
- Treasury,
- USAspending,
- selected public finance/government accounts.

### Elections/political finance

- FEC,
- election results,
- candidates,
- committees,
- campaign contributions/expenditures,
- congressional financial disclosures.

### Public safety

- FBI UCR/NIBRS,
- reporting coverage,
- agencies,
- offenses/arrests/incidents where appropriate.

### Documents/research

- laws,
- bill text,
- hearings,
- reports,
- public-source documents,
- search/chunk/embedding layer.

---

## Move out of OpenDiscourse

The current canonical model still contains:

```text
core.instrument
core.instrument_symbol
fact.market_bar
```

Those are not public-policy core entities.

They should move to or be deprecated in favor of:

```text
cbwinslow/cfa-knowledge-base
```

OpenDiscourse should retain:

- macro series,
- rates,
- inflation,
- employment,
- income,
- regional economic measures,
- public fiscal data.

CFA should own:

- equity/security master,
- stock prices,
- options,
- corporate fundamentals,
- valuation,
- portfolio analytics,
- trading/market microstructure.

Congressional security transactions can live canonically as **public disclosure events** in OpenDiscourse, while CFA may consume them and resolve securities against its security master.

That boundary is clean.

---

# 5. Source acquisition principle

Use this as a permanent project rule:

> **Bulk-first for historical bootstrap, API/feed-first for incremental freshness, immutable evidence always, canonical normalization under our control.**

This is not absolute. It is a default decision heuristic.

## Why bulk is preferable for history

Bulk sources generally provide:

- fewer HTTP calls,
- reproducible snapshots,
- easier checksumming,
- lower rate-limit risk,
- better backfill speed,
- easier coverage reconciliation,
- source-native archival evidence.

## Why APIs remain necessary

APIs are better for:

- incremental updates,
- metadata discovery,
- small corrections,
- recently changed records,
- operational freshness,
- source coverage checks.

The project should support both for many providers.

---

# 6. Federal legislative data — recommended source architecture

This is one of the most important areas to get right.

No single federal source is sufficient by itself.

## 6.1 Congress.gov API

Use for:

- current bill metadata,
- members,
- actions,
- amendments,
- committees,
- cosponsors,
- related bills,
- subjects,
- summaries,
- text metadata,
- hearings,
- committee meetings,
- committee reports,
- committee prints,
- nominations,
- treaties,
- communications,
- other collections exposed by API v3.

The official API currently:

- uses v3,
- supports JSON/XML,
- has pagination up to 250 records,
- publishes coverage documentation,
- publishes a changelog,
- has a 5,000 request/hour limit,
- and contains update timestamps/filtering on many resources.

### Python approach

The Library of Congress repository includes an example Python client and endpoint examples.

Do not copy that client blindly into OpenDiscourse.

Instead:

- use it as a reference,
- inspect whether it satisfies retries/pagination/raw-response needs,
- either wrap it or keep the existing `httpx` transport if our evidence requirements are stronger.

The important objective is not “use the most libraries possible.”

The objective is:

> **avoid custom work when a maintained implementation already provides the required behavior without losing provenance or control.**

---

# 7. GovInfo — federal bulk backbone

GovInfo is the correct bulk source for many federal legislative documents.

## High-value collections

### BILLSTATUS

Use as a primary bulk source for modern federal legislation.

It provides structured bill-status XML and is appropriate for:

- bills,
- actions,
- sponsors/cosponsors,
- committees,
- subjects,
- text-version metadata,
- other legislative status details.

The existing GovInfo artifacts and reconciliation work in OpenDiscourse are valuable.

### BILLS

Use for official bill text/document packages.

### BILLSUM

Use for official legislative summaries where available.

### Congressional Record

Use for floor proceedings and text analysis.

### Statutes at Large

Use for enacted-law history.

### Other GovInfo collections

Potential future additions:

- committee reports,
- hearings,
- Congressional documents,
- federal publications.

## Recommended relationship

```text
GovInfo bulk
    ↓
immutable artifact lake
    ↓
bulk parser/stager
    ↓
canonical legislation/documents

Congress.gov API
    ↓
incremental/raw payload
    ↓
reconcile/enrich/update
```

Neither replaces the other.

---

# 8. Federal roll-call votes

Do not rely on the current Congress.gov House-vote API as the universal federal vote solution.

The current Congress.gov roll-call support does not cover the full historical House+Senate research problem.

## Primary evidence

### House

Official House Clerk roll-call XML.

### Senate

Official Senate roll-call XML from the Senate legislative information system/pages.

The Senate XML includes:

- vote number,
- date,
- question,
- result,
- issue/nomination relationship,
- totals,
- individual member positions.

## Reuse `unitedstates/congress`

The established `unitedstates/congress` project already:

- downloads official bulk bill-status data,
- parses legislation,
- downloads GovInfo documents,
- scrapes House roll-call votes,
- scrapes Senate roll-call votes,
- outputs structured data.

This should be reused.

### Important distinction

Treat it as an **acquisition/parser producer**, not as the source of truth.

Ideal pipeline:

```text
official House/Senate endpoint
        ↓
unitedstates/congress acquisition/parser
        ↓
official XML retained as immutable evidence
        +
normalized upstream JSON
        ↓
OpenDiscourse stage
        ↓
OpenDiscourse canonical transform
```

This lets us benefit from years of community work without outsourcing our canonical semantics.

---

# 9. Congressional identity and memberships

`unitedstates/congress-legislators` is one of the most valuable upstream projects for this domain.

It provides:

- current legislators,
- historical legislators back to 1789,
- term history,
- committees,
- current committee assignments,
- Bioguide IDs,
- FEC IDs,
- GovTrack IDs,
- Voteview/ICPSR IDs,
- OpenSecrets IDs,
- VoteSmart IDs,
- C-SPAN IDs,
- other useful crosswalks.

## Use Bioguide as primary federal external identity

This agrees with the project’s current direction.

But canonical identity should not depend on only one identifier.

Use:

```text
core.person
core.person_identifier
```

with multiple identifier assertions.

Do not name-match federal legislators except as an explicit, reviewable entity-resolution fallback.

---

# 10. OpenStates acquisition strategy

The current idea of restoring the monthly PostgreSQL dump into a separate `openstates` database is **good**.

The current idea of treating its FDW schema as a stable researcher-facing contract is **not**.

OpenStates explicitly describes its PostgreSQL dump as nearly complete and frequently refreshed, but says the dump is only supported for restoring a development database and that internal schema changes are not guaranteed.

Therefore:

```text
OpenStates monthly dump
        ↓
separate source database
        ↓
FDW/internal source reader
        ↓
stable OpenDiscourse normalizer
        ↓
core/fact
```

FDW remains an implementation detail.

Researchers should not be told to depend on:

```text
openstates_source.opencivicdata_*
```

as a long-term API.

## Incremental freshness

OpenStates API v3 supports current data and search.

OpenStates also maintains `pyopenstates`, a Python API v3 client.

Recommended use:

- monthly dump for bulk baseline,
- API v3 for targeted/current reconciliation if needed,
- evaluate `pyopenstates` as the client before maintaining custom REST plumbing,
- retain raw responses or source identifiers required for provenance.

---

# 11. Legislative data model — important redesign

The current model is close to Open Civic Data/OpenStates but not yet complete enough to become the long-lived canonical contract.

This should be corrected **before** large new federal/state integrations.

## 11.1 Add Post / Seat / Office

Current membership is roughly:

```text
person
  ↓
membership
  ↓
organization
```

That loses an important relationship.

Correct conceptual shape:

```text
Jurisdiction
    ↓
Organization/chamber
    ↓
Post / seat
    ↓
Membership
    ↓
Person
```

A `Post` represents things such as:

```text
Virginia House District 17 seat
North Carolina Senate District 4 seat
U.S. House VA-06
U.S. Senate Virginia Class 1 seat
committee chair position
```

Useful fields:

```text
post_id
organization_id
division_id / represented_area_id
source identifier
label
role
start_date
end_date
maximum_memberships
metadata
```

Membership then contains:

```text
membership_id
person_id
organization_id
post_id nullable
role
label/title
start_date
end_date
source identity
source evidence
```

This is the correct basis for temporal representation research.

---

# 12. Add a political division / represented-area concept

Do not assume every political district is simply a current Census GEOID.

Redistricting creates temporal identity problems.

Recommended concept:

```text
core.division
```

or an equivalent political-area model containing:

```text
division_id
ocd_division_id
classification
label
jurisdiction_id
valid_from
valid_to
```

Then link a division to one or more geography/boundary representations.

This separates:

```text
political identity
```

from:

```text
a particular spatial polygon vintage
```

That distinction is important for longitudinal research.

---

# 13. Organization model should be hierarchical

Current organization modeling is too minimal.

Recommended fields/relations:

```text
organization_id
classification
name
jurisdiction_id
parent_organization_id
founding_date
dissolution_date
metadata
```

Classifications can include:

```text
legislature
upper
lower
committee
subcommittee
party
agency
```

The hierarchy supports:

```text
U.S. Congress
 ├── House
 │    ├── Committee
 │    └── ...
 └── Senate
      ├── Committee
      └── ...
```

This mirrors real legislative structures and established civic-data practice.

---

# 14. Membership should become fully temporal and source-addressable

Current membership already has dates and evidence, which is good.

Add:

- source-native membership identifier,
- optional post,
- raw source label/title,
- classification,
- represented division/post relation,
- potentially date range generated from start/end.

PostgreSQL range types plus `btree_gist` exclusion constraints can enforce temporal rules when appropriate.

Example use:

Prevent two incompatible active memberships from occupying a single-member post over overlapping date ranges, while allowing multi-member seats explicitly.

Do not add such constraints until historical edge cases are tested.

---

# 15. Person and identifier provenance needs strengthening

A canonical person can be asserted by several independent sources.

Do not make `core.person` itself “belong” to Congress.gov or OpenStates.

Instead retain source assertions.

At minimum, identifier mappings should include evidence:

```text
person_id
namespace
external_id
valid_from
valid_to
source_artifact_id / source_payload_id
source_record_key
```

Potential namespaces:

```text
bioguide
openstates
ocd-person
fec-candidate
icpsr
lis
govtrack
opensecrets
votesmart
cspan
```

This turns person identity into a verifiable crosswalk rather than an implicit join.

---

# 16. Generic identity-resolution subsystem

The current identity-exception model is too federal-vote-specific.

It currently encodes concepts such as:

```text
congress
kind = voter
```

in generic ingestion infrastructure.

Replace it with something domain-neutral.

Suggested concepts:

```text
identity.assertion
identity.resolution
identity.exception
```

or similar.

An unresolved record should retain:

```text
dataset
entity_type
namespace
external_id
raw_name
source_record
reason
first_seen
last_seen
attempt_count
resolution_state
```

Examples:

```text
unresolved FEC candidate
unresolved OpenStates voter
unresolved congressional sponsor
unresolved committee code
unresolved disclosure filer
```

One subsystem should support all of them.

---

# 17. Bill model redesign

Current federal-style fields:

```text
jurisdiction
legislative_session
bill_type
bill_number
```

are convenient for Congress but too federal-centric as the core universal identity.

Recommended universal core:

```text
bill_id
legislative_session_id
from_organization_id
identifier
title
classification[]
introduced_at
metadata
```

Examples of `identifier`:

```text
HB 264
SB 12
H.R. 1
S. 42
HJRES 5
```

Retain federal convenience fields either:

- as a federal extension,
- as generated/parsing attributes,
- or as source identifiers.

Do not let federal bill-type semantics define every state bill.

## Bill identifiers

Retain:

```text
OCD bill ID
Congress/type/number
GovInfo package ID
source-specific IDs
```

as first-class identifiers.

---

# 18. Bill actions

The current action model is a good start.

Add/ensure:

```text
organization_id
description
occurred_at
classification[]
source order
source evidence
related vote
related entities
```

A source action is often more valuable than a derived “latest action” string.

The canonical model should preserve the action timeline.

---

# 19. Sponsorships

Current sponsorship assumes a person and a `sponsor/cosponsor` role.

That is too narrow for cross-state data.

OpenStates supports:

- raw sponsor name,
- person or organization sponsor,
- source classification,
- primary sponsor indicator.

Recommended:

```text
bill_sponsorship
  bill_id
  raw_name
  entity_type
  person_id nullable
  organization_id nullable
  primary boolean
  classification
  source evidence
```

Federal `sponsor/cosponsor` can map naturally without constraining state semantics.

---

# 20. Votes

Current `roll_call` + `member_vote` is a sound basic split, but should be expanded.

## Vote event

Recommended fields:

```text
vote_event_id
session_id
organization_id
source_identifier
occurred_at
motion_text
motion_classification[]
result
bill_id nullable
bill_action_id nullable
source evidence
```

Do not require a bill.

Important federal roll calls include:

- nominations,
- procedural votes,
- cloture,
- leadership elections,
- resolutions,
- amendments,
- other matters.

## Vote counts

Add:

```text
vote_count
  vote_event_id
  option
  value
```

## Person vote

Retain both:

```text
raw_voter_name
raw_voter_identifier
resolved_person_id nullable
option
note
source evidence
```

Do **not** discard a vote merely because identity resolution failed.

That is a critical provenance rule.

---

# 21. Bill documents need manifestations

A document/version can have:

- PDF,
- HTML,
- XML,
- plain text.

Do not create four unrelated canonical documents if they represent the same content/version.

Model:

```text
document
   ↓
document_manifestation
```

Manifestation fields:

```text
media_type
url
checksum
artifact_id
text_extraction_status
```

This matches established legislative data models and improves retrieval/search.

---

# 22. Hearings, meetings, nominations, treaties, and other actions

The Congress.gov API exposes much more than bills.

Useful next domains include:

- committee meetings,
- hearings,
- committee reports,
- committee prints,
- nominations,
- treaties,
- House/Senate communications,
- CRS reports where available.

Do not immediately create one giant `government_event` abstraction.

Start with a reusable event foundation only where the commonality is real.

For example:

```text
core.event
event_organization
event_document
event_bill
```

may work well for hearings/meetings.

Nominations and treaties have richer domain-specific lifecycles and may deserve dedicated domain tables.

**Generalize from proven commonality, not from aesthetic desire.**

---

# 23. Open Civic Data should remain a cornerstone, not a prison

The prior decision to align legislative entities with Open Civic Data is sound.

What should change is how strictly it is interpreted.

Recommended principle:

> Use Open Civic Data/OpenStates/Popolo as the interoperability baseline for shared legislative concepts. Add domain extensions where federal or research requirements genuinely exceed the model.

Do not:

- force unrelated economic facts into OCD,
- force every federal proceeding into “bill,”
- mirror OpenStates’ internal database schema,
- or sacrifice provenance/research requirements merely for shape compatibility.

---

# 24. Provenance redesign

Current source evidence is already better than most research projects.

Keep the core principle, but improve how merged entities are represented.

## Source evidence vs canonical identity

A canonical entity may have evidence from many sources.

Therefore avoid assuming:

```text
canonical_entity.source_payload_id
```

is enough.

Prefer:

```text
canonical entity
    ↓
source assertion / identifier / relation
    ↓
immutable evidence
```

Potential model:

```text
provenance.source_record
provenance.entity_assertion
```

or equivalent domain-specific mapping tables.

A source record can identify:

```text
dataset_id
artifact_id or payload_id
source_record_key
source_url
observed_at
valid_from / valid_to
checksum
```

An assertion can explain:

```text
canonical entity
source record
resolution method
resolver version
confidence/review state
```

This is especially valuable when:

- Congress.gov and GovInfo disagree,
- OpenStates has a corrected person name,
- a FEC candidate ID maps to a Bioguide member,
- a district changes over time.

---

# 25. Raw API payloads vs bulk artifacts

Do not store gigantic bulk datasets again as JSONB raw payloads.

Use two evidence paths intentionally.

## API

```text
ingest.raw_payload
```

works for bounded HTTP responses.

## Bulk files

Use:

```text
ingest.artifact
source member/file
source row ordinal
```

and immutable checksums.

Stage rows can reference:

```text
artifact_id
member
ordinal
```

That is sufficient reproducibility without duplicating large source archives inside PostgreSQL.

---

# 26. Cursor model cleanup

The project currently has more than one cursor concept.

Consolidate around one generic checkpoint model if possible:

```text
dataset/plan
partition/shard key
cursor state
successful run
updated_at
```

The cursor payload can remain JSONB because provider cursor semantics differ.

But the lifecycle and ownership should be singular and explicit.

---

# 27. Census architecture

The existing Census strategy is fundamentally strong.

## ACS

For comprehensive research:

**Official ACS Summary Files should remain the primary historical/bulk source.**

They contain detailed-table estimates and margins of error across published geographies.

Use Census API for:

- metadata discovery,
- field definitions,
- small user-selected pulls,
- coverage validation,
- targeted current queries.

Useful Python libraries such as DataMade’s `census` package are excellent for interactive/API convenience but are not a replacement for bulk Summary File ingestion.

## TIGER/Line

Continue official annual bulk shapefile acquisition.

Retain:

- boundary vintage,
- geography identity,
- validity interval where known,
- source artifact.

## PEP

Continue release-vintage modeling.

Never silently merge vintages.

## CBP

Continue official annual bulk.

This is a good example of a source-specific fact table being better than forcing everything into a generic measurement EAV structure.

---

# 28. BLS redesign

The current BLS dataset is still pilot-scale and should be treated as such.

Current weaknesses include:

- tiny curated series count,
- stale date range,
- little/no local geography,
- no meaningful QCEW population.

## QCEW

Use official downloadable QCEW CSV/bulk files.

QCEW has long historical coverage and is designed for downloadable data.

Do not make a generic BLS API client fetch millions of historical QCEW rows unnecessarily.

## LAUS / CPI / CES / other LABSTAT programs

Prefer official bulk flat files for historical/full-series bootstrap when available.

Use API calls for:

- selected series,
- incremental refresh,
- user queries.

Create explicit source-family adapters instead of a vague `BLSConnector` that pretends all BLS products have identical grains.

---

# 29. BEA

Evaluate and likely adopt the official `us-bea/beaapi` package for API interaction.

It is maintained under the U.S. BEA organization and makes metadata/data access easier.

Still preserve:

- requested parameters,
- response evidence,
- release/vintage semantics where available.

For large BEA datasets, use official downloadable data if more efficient than repeated API requests.

---

# 30. FRED / ALFRED

The existing FRED work is useful.

I would slightly adjust the implementation philosophy.

`fredapi` is convenient, particularly for ALFRED/vintage access, but the warehouse’s core ingest path benefits from retaining exact raw responses and request metadata.

Recommended:

- direct official FRED API via existing `httpx` infrastructure for canonical ingestion,
- `fredapi` as optional reference/analyst convenience,
- explicitly model real-time/vintage dates,
- manifest the approved core series list in version control.

FRED should remain a reference source for the new connector runtime because it is small enough to reason about.

---

# 31. Treasury

Keep the working Treasury yield-curve path.

Add other Fiscal Data domains only when a research use case is defined.

Do not add every Treasury endpoint simply because it exists.

---

# 32. USAspending

This domain has strong reuse opportunities.

Use:

- official bulk/archive/database downloads for historical bootstrap,
- official API for focused/incremental access.

Evaluate the maintained `usaspending-orm` package before creating a broad custom client.

It already includes:

- typed models,
- query builders,
- exact Decimal amounts,
- pagination,
- retries,
- rate limiting,
- optional caching,
- raw responses,
- bulk download support.

If it satisfies our evidence contract, wrap it.

If it loses required details, keep only the parts that help.

---

# 33. FEC

The current decision to use official bulk files is correct.

## Historical/bootstrap

Use official FEC bulk transaction files.

## Incremental/current/query

Use OpenFEC API.

## Important correction to current BMAD plan

**Do not block acquisition/staging of FEC on congressional identity resolution.**

These are independent concerns.

Correct pipeline:

```text
FEC bulk
  ↓
stage using FEC candidate/committee IDs
  ↓
canonical FEC-native finance facts
  ↓
optional identity enrichment
  ↓
candidate/member/person crosswalk
```

Identity is necessary for cross-domain politician analysis.

Identity is **not** necessary to preserve or load authoritative FEC data.

That distinction reduces unnecessary dependencies.

---

# 34. Congressional financial disclosures

This is an important domain, but it needs legal/terms awareness and careful semantics.

## House

Official annual financial-disclosure indexes and reports are available.

## Senate

The Senate electronic financial-disclosure system is more awkward/session-oriented.

Reuse community download/parsing projects where helpful, but preserve the official filing artifact as source evidence.

## Important model rule

Do not convert disclosure ranges into fake exact transaction values.

Retain:

```text
reported range minimum
reported range maximum
transaction date
filing date
asset description
owner
transaction type
filing/report ID
raw official document
```

Security resolution into CFA’s instrument master should be a separate enrichment process.

## Usage/redistribution policy

Document House/Senate disclosure terms and redistribution restrictions before publishing bulk derived copies.

---

# 35. Elections

Recommended sources depend on grain.

## Research-ready historical federal/state returns

MIT Election Data + Science Lab is a strong research source.

It currently publishes, among other datasets:

- U.S. House 1976–2024,
- presidential data,
- Senate data,
- state returns,
- 2024 precinct data.

## Source-native state election results

OpenElections is valuable because it preserves official source files and converted standardized data.

Use:

```text
official state source
    ↓
OpenElections where available
    ↓
OpenDiscourse staging
```

Do not pretend election data is nationally uniform.

The model must represent:

- election,
- contest,
- office/post,
- district,
- candidate,
- party/ballot label,
- reporting unit,
- vote count,
- certification/source status.

---

# 36. FBI crime data

The FBI Crime Data Explorer should be the authoritative federal starting point.

It exposes:

- downloadable CSV data,
- large downloadable files,
- NIBRS,
- Summary Reporting System data,
- hate crime,
- arrests,
- homicide,
- law-enforcement data,
- participation/coverage information.

## Critical modeling requirement

**Never analyze crime counts without reporting coverage.**

Agency participation changes over time.

The FBI itself distinguishes:

- participating agencies,
- complete months,
- population coverage,
- NIBRS vs SRS,
- estimated vs reported values.

Therefore a crime model should retain:

```text
reporting system
agency
period
offense
reported/estimated indicator
months reported
population covered
coverage rate
source release
```

## Important BMAD correction

Crime ingestion should **not** be blocked on congressional person identity.

It is a geography/agency domain.

Identity work and crime work can proceed independently.

---

# 37. Other government actions worth adding later

Once the legislative spine is correct, high-value additions include:

## Federal legislative proceedings

- hearings,
- committee meetings,
- committee reports,
- committee prints,
- nominations,
- treaties,
- Congressional Record.

## Regulatory activity

Future expansion could include:

- Federal Register documents,
- regulations/dockets,
- executive actions/presidential documents.

## Spending/procurement

USAspending.

## Courts/legal

Potential later domain:

- CourtListener / RECAP where licensing/terms permit,
- federal opinions,
- agency adjudications.

Do not add all of these before the v2 canonical foundation is stable.

---

# 38. Generic fact model vs specialized facts

The current project uses both:

```text
fact.measurement
```

and source/domain-specific fact tables.

That is the correct direction.

## Use `fact.measurement` for

```text
dataset × field × geography × period × vintage → scalar value
```

Examples:

- selected ACS-style measures,
- FRED,
- BLS series,
- BEA scalar measures,
- Treasury series,
- some crime aggregates.

## Use specialized fact tables when

- source grain is large or complex,
- multiple measures always travel together,
- source-specific dimensions matter,
- EAV creates difficult queries,
- the domain has relationships/events rather than scalar observations.

Examples:

- CBP,
- roll-call votes,
- FEC transactions,
- election returns,
- financial disclosures,
- NIBRS incidents,
- USAspending awards/transactions.

Do not try to make one fact table “universal.”

---

# 39. Research marts should be the user-facing product

Researchers should not need to understand every ingestion/source schema.

dbt should produce stable marts such as:

```text
mart_place_year
mart_county_year
mart_state_year
mart_congressional_district_year
mart_legislator_term
mart_legislator_vote
mart_bill_lifecycle
mart_bill_sponsorship
mart_committee_membership
mart_campaign_finance
mart_election_result
mart_crime_area_year
mart_policy_exposure
mart_financial_disclosure
```

These become the primary analyst contract.

Canonical tables preserve normalized truth.

Marts optimize research ergonomics.

---

# 40. Search and embeddings

The repo already has:

- Postgres full-text search,
- trigram search,
- document chunks,
- an embedding concept.

But the current embedding storage is an ordinary `REAL[]`.

If semantic search remains in scope, use actual `pgvector`.

Recommended schema:

```text
search.embedding
  embedding_id
  chunk_id
  model
  model_version
  dimensions
  embedding vector(N)
  created_at
```

Create the appropriate HNSW index only after measuring corpus/query size.

Keep:

- document text,
- full-text search,
- pg_trgm,
- vector search.

Use hybrid ranking where useful.

Do not introduce Qdrant/Weaviate/Elasticsearch yet.

PostgreSQL can handle the initial workload while preserving easy relational joins.

---

# 41. PostgreSQL extensions/features to deliberately use

## Keep

### PostGIS

Essential.

### pgcrypto

Useful for UUID/checksum-related capabilities where needed.

### pg_trgm

Excellent for:

- name lookup,
- title lookup,
- fuzzy identifiers,
- researcher search.

### unaccent

Useful paired with text search.

---

## Add / activate

### pgvector

If semantic document search is retained.

Do not keep fake vector arrays once actual vector search is implemented.

### pg_stat_statements

Enable on production/development database servers.

It provides real evidence about:

- slow queries,
- frequently executed queries,
- planning/execution time.

Optimize based on measurements rather than guesses.

### btree_gist

Useful for temporal exclusion constraints involving:

- post occupancy,
- memberships,
- symbol/identifier validity,
- other range-overlap rules.

Use after historical edge cases are understood.

---

## Use built-in PostgreSQL features before extensions

### Range types

Use `daterange` / `tstzrange` for time-valid relationships when appropriate.

### BRIN indexes

Potentially excellent for very large naturally ordered tables such as:

- ACS fact loads by release/year,
- timestamped events,
- source-row/ingestion ordering,
- large transaction facts.

They are dramatically smaller than giant B-tree indexes where physical correlation exists.

### Partial indexes

Useful for:

- current records,
- unresolved identities,
- active memberships,
- records with optional external IDs.

### Materialized views

Potentially useful for expensive stable research summaries, though dbt tables are often a cleaner warehouse pattern.

---

## Do not add yet

### TimescaleDB

Not needed for current workload.

This is not primarily a high-frequency telemetry/time-series service.

### pg_partman

Only add after actual partition maintenance pain exists.

### pg_cron

Useful for database-local maintenance, but it should not become the external government-data orchestrator.

---

# 42. Bulk loading performance

For large stages:

**Use PostgreSQL COPY through psycopg3.**

It is one of the most efficient supported data-loading paths.

Recommended:

```text
source file
   ↓
Polars / PyArrow / streaming parser
   ↓
typed validation/conversion
   ↓
psycopg COPY
   ↓
stage table
   ↓
SQL transform/upsert
```

Do not perform hundreds of millions of individual ORM inserts.

## PostgreSQL 17 advantage

`COPY ... ON_ERROR` now provides additional loading options, though canonical pipelines should still explicitly define their reject/error policy.

## Small batches

SQLAlchemy’s normal insert batching is fine.

## Many small independent statements

Psycopg pipeline mode can help reduce round trips.

COPY and pipeline mode serve different purposes.

---

# 43. Python persistence stack

Current stack overlaps:

- SQLModel,
- SQLAlchemy,
- psycopg.

That is more abstraction than the warehouse really needs.

## Recommendation

Gradually converge on:

```text
SQLAlchemy 2 Core / ORM
+
psycopg3 driver
+
direct psycopg COPY for bulk hot paths
+
Pydantic for external/config/domain validation
+
Alembic for schema migrations
```

### Why reconsider SQLModel

Most of the core/fact warehouse is already declared as SQLAlchemy `Table` objects attached to `SQLModel.metadata`.

That means SQLModel is not buying much in those modules.

Use plain SQLAlchemy `MetaData` for warehouse contracts.

If a handful of catalog models benefit from ORM classes, use SQLAlchemy 2 typed `Mapped[]` classes or retain SQLModel temporarily until migration is justified.

Do not make dropping SQLModel a big-bang prerequisite.

Treat it as a simplification migration.

---

# 44. HTTP/API stack

Current choices are good:

```text
httpx
tenacity
pydantic
pydantic-settings
```

Keep them.

Do not add another HTTP client merely because an upstream package uses `requests`.

If adopting a third-party API client, isolate it behind our source adapter.

---

# 45. Parsing stack

Recommended:

## JSON

Standard library is usually sufficient.

`orjson` is optional if profiling proves JSON parsing is material.

## XML

Use:

- standard ElementTree for straightforward files,
- `lxml` for large GovInfo/Congress XML or XPath/namespace-heavy processing where it improves performance/clarity.

## CSV/tabular

Use:

- PyArrow,
- Polars,
- Python `csv` for streaming/simple fixed schemas.

Avoid pandas as a mandatory ingestion dependency when Polars/Arrow already cover the bulk path efficiently.

## Geo

Keep:

- pyogrio,
- shapely,
- geopandas where needed,
- PostGIS for canonical spatial storage.

---

# 46. dlt

Keep `dlt` as an **optional acquisition/staging tool**, not as the canonical architecture.

Good use:

```text
generic REST endpoint
  ↓
dlt
  ↓
stage/raw
```

Poor use:

```text
every custom ZIP/XML/bulk/government format
  ↓
forced through dlt
```

Provider-specific bulk loaders can be simpler and more robust without it.

---

# 47. dbt

Keep and expand dbt.

It is an excellent fit for:

- research marts,
- data tests,
- dimensional transformations,
- documented analytical relations,
- reproducible derived metrics.

Do not use dbt for source acquisition.

---

# 48. DuckDB

Keep DuckDB as an analytical/export sidecar.

High-value uses:

- scanning Parquet,
- exporting Postgres result sets,
- analyst-local workflows,
- joining local Parquet packs,
- validating large files before load.

PostgreSQL remains the system of record.

---

# 49. Prefect

Keep Prefect optional.

Do not make Prefect a prerequisite for basic local operation yet.

When the source graph grows large enough that you need:

- visible schedules,
- retries,
- backfills,
- dependency orchestration,
- operational dashboards,
- distributed workers,

Prefect is a reasonable next step.

The Connector/runtime should not depend on Prefect-specific types.

---

# 50. Repository/package organization

The current top-level package still contains large modules such as `cli.py` and `browser.py`, plus source-specific logic spread across `providers/` and `ingestion/`.

Target structure:

```text
src/opendiscourse_research/
    core/
        config.py
        contracts.py
        errors.py

    acquisition/
        protocol.py
        runtime.py
        evidence.py
        checkpoint.py
        capacity.py

    sources/
        congress/
        govinfo/
        congress_votes/
        openstates/
        census/
        fred/
        bls/
        bea/
        treasury/
        fec/
        usaspending/
        fbi/

    domains/
        legislative/
        identity/
        geography/
        economics/
        elections/
        campaign_finance/
        disclosures/
        crime/
        documents/

    persistence/
        database.py
        bulk.py
        repositories/

    services/
        identity_resolution/
        validation/
        reconciliation/

    access/
        exports/
        search/
        api/

    cli/
        root.py
        ingest.py
        catalog.py
        admin.py
        export.py
```

Exact names can change.

The important principle is ownership.

Source adapters should not become domain models.

Domain models should not make HTTP calls.

CLI should not contain provider implementation.

---

# 51. Source registry

Remove the hard-coded `HANDLERS` pattern.

But do not replace it with magical auto-discovery that is hard to debug.

Use an explicit typed registry:

```python
registry.register(
    "fred",
    FredSource(...)
)
```

or entry points once external third-party plugins genuinely exist.

Internal registration should stay easy to inspect.

---

# 52. Testing architecture

The goal is not “run everything constantly.”

The goal is **maximum useful feedback per second**.

## Layer 1 — pure unit

Examples:

- parsers,
- identifiers,
- date logic,
- source URL generation,
- plan generation,
- transformation functions.

No DB.

No network.

Run constantly.

---

## Layer 2 — fixture contract

Real representative source payloads checked into fixtures.

Examples:

```text
Congress bill response
GovInfo BILLSTATUS XML
House vote XML
Senate vote XML
OpenStates API response
FEC row
BLS file sample
```

Tests should prove:

```text
source fixture
    ↓
parser
    ↓
expected typed staging/domain records
```

No live network.

No DB when possible.

---

## Layer 3 — property-based

Hypothesis is already installed.

Use it for:

- identifier parsing,
- date ranges,
- cursor serialization,
- pagination,
- decimal handling,
- idempotency properties,
- generated malformed source records.

---

## Layer 4 — DB integration

Use PostGIS only when database semantics are actually under test:

- constraints,
- migrations,
- COPY,
- repositories,
- upsert/idempotency,
- spatial joins,
- temporal exclusion,
- transaction behavior.

---

## Layer 5 — source integration/live smoke

Run against live government endpoints only:

- nightly,
- scheduled,
- manually,
- or in dedicated smoke workflows.

These tests detect upstream contract drift.

They should not gate every developer commit.

---

## Layer 6 — reconciliation/data quality

Examples:

```text
expected bills per Congress
expected vote count range
OpenStates snapshot count checks
FEC archive row totals
ACS source/table coverage
no orphan memberships
all canonical identifiers trace to evidence
```

These are often more valuable than conventional unit coverage for a research warehouse.

---

# 53. CI redesign

Current CI has improved, but the full PostGIS suite still runs on every PR.

Target:

## Required PR Fast

Target roughly <30–45 seconds.

Run:

```text
ruff check
ruff format --check
ty check
fast non-DB pytest with xdist
configuration/inventory validation
BMAD/spec validation if inexpensive
changed SQL lint
```

## Affected integration

Run only when relevant paths change.

Examples:

```text
models/migrations/persistence
    → DB integration

sources/congress
    → congress fixture + related DB integration

sources/census
    → census tests

dbt/
    → dbt compile/test subset
```

## Full main

All deterministic tests.

## Nightly

- all integration,
- live-source smoke,
- long reconciliation,
- mutation tests if adopted,
- expensive data-quality checks,
- performance benchmarks.

---

# 54. CI path classification

Create a small project-owned classifier rather than depending on a pile of third-party GitHub Actions.

Example output:

```text
python=true
database=true
legislation=true
census=false
dbt=false
docs=true
```

A single required `ci-gate` job can summarize whether every **required-for-this-change** job succeeded.

This avoids the GitHub problem where a required job is skipped due to path filters and leaves confusing branch-protection behavior.

---

# 55. Database-test speed

Recommended strategy:

## Do not boot a new Postgres container per test.

Use one service/container per job.

## Reset state cheaply

Options:

- transaction-per-test + rollback,
- isolated schema per worker,
- template database clones for expensive schema initialization.

## Parallel DB tests

Only once each worker has isolation:

```text
gw0 → test schema/db 0
gw1 → test schema/db 1
...
```

Until then, keep mutable DB tests serial.

---

# 56. CI quality checks currently missing from enforcement

The repository already installs tooling that the fast script does not yet fully execute.

Add:

```text
ruff format --check
ty check
sqlfluff lint <changed SQL/dbt SQL>
```

Also add focused validations for:

- YAML contracts,
- source inventory,
- migration rendering,
- documentation crosslinks where cheap.

Do not turn the fast lane into a 5-minute mega-check.

---

# 57. Coverage policy

Do not pursue 100% line coverage as the primary objective.

For this project, more important metrics are:

- every source parser has fixture coverage,
- every canonical transform has meaningful tests,
- every migration is exercised,
- every critical constraint has a failing-case test,
- every bug gets a regression test,
- every connector has idempotency/restart tests,
- every important dataset has reconciliation checks.

Coverage percentage can remain a signal.

It is not the quality definition.

---

# 58. BMAD remains the right methodology

Keep BMAD.

Its current brownfield philosophy is actually aligned with this review:

- inspect the existing codebase,
- keep project context small,
- avoid feeding stale PRDs into every task,
- use the architecture workflow for real tradeoff decisions,
- use lightweight Build for small changes,
- use specs/projects for larger changes.

TEA also fits extremely well because this project needs risk-based testing and selective CI.

---

# 59. BMAD plan changes

The current BMAD epic plan should be **superseded in several places**.

## Keep

- development substrate,
- short AGENTS context,
- ADR system,
- project skills,
- GitHub ruleset,
- registry goal,
- identity crosswalk,
- reuse of `unitedstates/congress`,
- dbt marts,
- PostgREST,
- streaming exports.

## Change

### Current Connector Story

Do not continue Story 2.2/2.3 using the 10-stage connector as unquestioned architecture.

First revise the Connector design.

### Identity gating

Current plan blocks:

```text
FEC/disclosure/crime
```

on Congress identity.

Change to:

```text
identity enrichment blocks cross-domain politician joins
```

not source ingestion.

Crime is unrelated and can proceed independently.

FEC can be captured/staged/canonicalized in FEC-native IDs without Bioguide mapping.

### OpenStates

FDW should remain an internal source access mechanism.

Add an explicit story to materialize a stable canonical OpenStates subset.

### Legislative model

Add a blocking architecture epic before federal vote/member expansion.

---

# 60. Proposed new BMAD program

## Epic A — Architecture reset and invariants

Stories:

1. Accept/supersede architecture decisions.
2. Define source/canonical/provenance boundaries.
3. Define v2 connector runtime.
4. Define canonical legislative model.
5. Define migration/parity strategy.

Exit condition:

No unresolved blocking architecture question for legislation/identity.

---

## Epic B — Legislative canonical model v2

Stories:

1. Add division/represented-area model.
2. Add post/seat.
3. Upgrade organization hierarchy.
4. Upgrade membership/source identity.
5. Upgrade bill universal identity.
6. Upgrade sponsorship.
7. Upgrade vote event/count/person vote.
8. Upgrade document manifestations.
9. Generic identity exceptions/assertions.
10. Data migration and compatibility views.

---

## Epic C — Connector runtime v2

Stories:

1. typed planning/acquisition results,
2. runtime-owned provenance/checkpoints,
3. explicit source registry,
4. bulk snapshot capability,
5. incremental API capability,
6. FRED migration as reference,
7. parity validation,
8. delete old HANDLERS path.

---

## Epic D — Federal legislative spine

Stories:

1. congress-legislators identity bootstrap,
2. GovInfo BILLSTATUS bulk,
3. Congress.gov incremental reconciliation,
4. official House votes,
5. official Senate votes,
6. `unitedstates/congress` wrapper,
7. committees,
8. amendments,
9. hearings/meetings,
10. research reconciliation checks.

---

## Epic E — OpenStates canonicalization

Stories:

1. source dump refresh contract,
2. FDW/source adapter,
3. post/membership transform,
4. bills/actions/sponsors transform,
5. vote transform,
6. canonical reconciliation,
7. v3 API incremental repair if needed.

---

## Epic F — Economic/public datasets

Independent tracks:

- BLS overhaul,
- BEA,
- USAspending,
- FRED manifest refinement,
- Treasury additions,
- Census remaining gaps.

---

## Epic G — Elections, campaign finance, disclosures, crime

Run partially in parallel.

Identity enrichment is a dependency only where joins require it.

---

## Epic H — Research product layer

- dbt marts,
- research packs,
- PostgREST,
- Parquet/GeoParquet export,
- R/Python examples,
- DuckDB workflows,
- browser/TUI cleanup.

---

# 61. What should be deleted or deprecated

Do not delete immediately; deprecate after replacement/parity.

Candidates:

## Architecture/code

- hard-coded `HANDLERS`,
- provider branches in generic registry/planning code,
- duplicated DB execution paths where SQLAlchemy and raw psycopg implement the same ordinary CRUD operation,
- the rigid 10-stage Connector once v2 replaces it,
- giant provider logic inside `browser.py`,
- giant command implementation inside `cli.py`,
- federal-specific identity exception fields in generic ingest code.

## Data/model

- `core.instrument`,
- `core.instrument_symbol`,
- `fact.market_bar` after CFA migration,
- `REAL[]` embeddings after pgvector migration,
- duplicated free-text jurisdiction/session identity once canonical foreign keys are complete.

## Documentation

Archive superseded planning documents.

Do not leave multiple “current architecture” documents that disagree.

---

# 62. What should explicitly remain

- Git history,
- BMAD,
- TEA,
- Serena,
- AGENTS hierarchy-of-truth idea,
- project skills,
- PostgreSQL 17,
- PostGIS,
- Alembic,
- pytest,
- Hypothesis,
- Ruff,
- ty,
- xDist,
- psycopg,
- SQLAlchemy,
- Pydantic,
- dbt,
- DuckDB,
- Polars/PyArrow,
- catalog/inventory/contracts,
- immutable evidence,
- capacity fail-closed behavior,
- data-lake artifacts,
- source coverage/reconciliation mindset.

---

# 63. Existing libraries/projects to evaluate or adopt

## Federal legislation

### LibraryOfCongress/api.congress.gov

Use official endpoint docs and Python examples as reference/client candidates.

### unitedstates/congress

**High priority reuse.**

Use as producer/parser for:

- bill status,
- documents,
- House votes,
- Senate votes.

### unitedstates/congress-legislators

**High priority reuse.**

Use for:

- historical/current members,
- terms,
- identifier crosswalk,
- committee metadata.

### Voteview

Use for:

- historical political-science research,
- ICPSR crosswalk,
- ideal-point measures,
- secondary validation.

Do not replace official vote evidence with Voteview.

---

## State legislation

### OpenStates / Plural Open

Use:

- PostgreSQL bulk dumps,
- official API v3,
- Open Civic Data semantics.

### pyopenstates

Evaluate/adopt for v3 API operations that retain sufficient response fidelity.

### openstates-core

Use as model/reference implementation.

Do not clone its entire internal schema as ours.

---

## Census

### DataMade census

Useful API convenience.

### censusdis

Potentially powerful discovery/geography convenience, but review its current license before making it a required production dependency.

### PyArrow / Polars

Preferred high-volume tabular tools.

---

## Economics

### beaapi

Strong candidate; maintained by U.S. BEA.

### fredapi

Optional convenience/reference.

### BLS

Prefer official bulk files/API rather than depending on an obscure wrapper.

---

## Spending

### usaspending-orm

Evaluate before writing another broad USAspending client.

### official usaspending-api source

Use as authoritative API behavior/reference.

---

## Campaign finance

### openFEC

Authoritative API implementation/reference.

Use official FEC bulk files for history.

---

## Elections

### MIT Election Data + Science Lab

Strong research-ready federal/state historical source.

### OpenElections

Strong official-source aggregation/conversion project.

---

## Search

### pgvector

Use actual PostgreSQL vector type/indexing.

---

# 64. Reuse decision checklist for every connector

Before writing a source client, an agent must answer:

1. Is there an official bulk download?
2. Is there an official API?
3. Is there an official Python client?
4. Is there an established community downloader/parser?
5. Does it preserve enough raw evidence?
6. Does its license permit our use/distribution?
7. Is it maintained?
8. Can it resume/retry?
9. Can we wrap it without adopting its canonical schema?
10. What unique code would OpenDiscourse still need?

Only then should custom implementation begin.

---

# 65. Data contract for every source

Every source adapter should document:

```text
source authority
license/terms
coverage dates
update cadence
grain
primary source keys
bulk location
API location
incremental cursor
known gaps
expected size
parser
staging table
canonical mapping
identity requirements
provenance path
validation checks
reconciliation method
```

This should be machine-readable where practical.

The existing inventory/contracts concept is an excellent home for this.

---

# 66. Validation philosophy

“Loaded successfully” must never mean “correct.”

Validation occurs at multiple levels.

## Transport

- HTTP status,
- content length,
- checksum,
- expected MIME type.

## Artifact

- archive opens,
- expected members exist,
- schema/version recognized.

## Stage

- row counts,
- type validity,
- required keys,
- reject counts.

## Canonical

- foreign keys,
- uniqueness,
- temporal consistency,
- identifier integrity,
- provenance.

## Reconciliation

- compare provider published counts,
- compare secondary source counts where appropriate,
- coverage by period/geography/session.

## Research

- known historical sanity checks,
- spot-check real bills/votes/districts/series.

---

# 67. No “perfect” data model exists

This is important.

The objective should not be:

> design the one final schema that will never change.

That is unrealistic for:

- government APIs,
- redistricting,
- revised economic releases,
- changing reporting standards,
- newly discovered source fields,
- source corrections.

The correct objective is:

> design a stable canonical model for the common research concepts, preserve every authoritative source snapshot, maintain explicit mappings, and make schema evolution safe.

That architecture remains correct even when sources change.

---

# 68. Migration plan

## Phase 0 — freeze architecture expansion

Continue:

- critical bug fixes,
- data integrity repairs,
- source freshness where necessary.

Pause:

- new canonical domains,
- new one-off connector frameworks,
- major new UI work.

---

## Phase 1 — write superseding BMAD architecture change

Create one BMAD project/change:

```text
OpenDiscourse v2 Foundation and Source Architecture Reset
```

Use this report as initial evidence, not as blindly accepted requirements.

BMAD should challenge/validate it against the codebase.

---

## Phase 2 — legislative schema in shadow/compatible form

Add new tables/columns with migrations.

Do not destructively rewrite loaded datasets.

Create compatibility views where needed.

---

## Phase 3 — Connector v2

Implement FRED first.

Prove:

- less code,
- equivalent evidence,
- same or better tests,
- easy registry,
- no HANDLERS branch.

Then migrate another structurally different source, ideally a bulk source, to prove the abstraction is not REST-specific.

---

## Phase 4 — federal identity + legislation

Load/normalize:

1. congress-legislators,
2. GovInfo bill status,
3. Congress.gov updates,
4. House votes,
5. Senate votes.

Run parity/reconciliation.

---

## Phase 5 — OpenStates canonical subset

Materialize the stable legislative research spine into our canonical tables.

Stop treating direct FDW queries as the researcher contract.

---

## Phase 6 — economics/public finance

Repair BLS and add BEA/USAspending according to research priority.

---

## Phase 7 — elections/FEC/disclosures/crime

Parallelize where dependencies allow.

---

## Phase 8 — marts/access

Publish stable researcher surfaces.

---

## Phase 9 — delete replaced architecture

Only after:

- parity tests pass,
- data reconciles,
- docs updated,
- migrations safe,
- no supported CLI path depends on old implementation.

---

# 69. Concrete first PRs

Do not make the first PR a thousand-file rewrite.

## PR 1 — Architecture decision reset

Docs/spec only:

- superseding BMAD architecture change,
- updated source acquisition principles,
- v2 legislative conceptual model,
- Connector v2 decision,
- migration strategy.

No schema change.

---

## PR 2 — CI truth

- `ruff format --check`,
- `ty check`,
- SQLFluff changed-file lane,
- path classifier,
- affected integration gating,
- DB marker cleanup.

Make feedback fast before large refactors.

---

## PR 3 — Legislative primitives

Add:

- division/represented area,
- post,
- organization hierarchy,
- membership upgrades,
- provenance/source IDs.

Migration only; no broad source loader.

---

## PR 4 — Vote model

Add:

- vote counts,
- raw voter identity,
- optional bill-action relationship,
- better source identifiers.

---

## PR 5 — Connector v2 skeleton + FRED

No broad source migration yet.

Prove the new runtime.

---

## PR 6 — congress-legislators loader

Identity foundation.

---

## PR 7 — GovInfo/Congress bill reconciliation

Use existing evidence.

---

## PR 8 — federal vote producer

Wrap `unitedstates/congress`, retain official XML.

---

# 70. Proposed success metrics

## Developer experience

- fast local checks <15 seconds for ordinary code,
- PR fast lane <45 seconds target,
- affected DB integration <90 seconds target where practical,
- no live-source calls in ordinary PR CI.

## Data integrity

- 100% canonical relationship rows traceable to evidence where source evidence is required,
- unresolved identities retained rather than dropped,
- no silent name matching,
- no silent vintage replacement.

## Source coverage

Maintain dashboards/reports for:

```text
source
expected coverage
loaded coverage
latest source release
latest successful refresh
validation state
```

## Research usability

A researcher should be able to answer common questions from `mart`/`api` without learning staging schemas.

---

# 71. Proposed architecture diagram

```text
                    OFFICIAL / TRUSTED SOURCES
                             │
     ┌───────────────────────┼─────────────────────────┐
     │                       │                         │
 BULK SNAPSHOT          API / FEED              COMMUNITY TOOL
 GovInfo/OpenStates     Congress/FRED/etc       unitedstates/congress
 Census/FEC/etc              │                         │
     └───────────────────────┼─────────────────────────┘
                             │
                             ▼
                     ACQUISITION ADAPTER
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
          immutable artifact       raw API payload
                 │                       │
                 └───────────┬───────────┘
                             ▼
                           STAGE
                 source-shaped records
                             │
                             ▼
                       NORMALIZATION
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          identity       canonical       validation/
          resolution       domain        reconciliation
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                     core / fact schemas
                             │
                             ▼
                           dbt
                             │
                             ▼
                         mart schema
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
        SQL              PostgREST          Parquet/
                                            DuckDB/R
```

---

# 72. BMAD handoff brief

The following can be pasted into BMAD as the intent for the next major change.

## Change title

**OpenDiscourse v2 Foundation and Source Architecture Reset**

## Intent

Re-evaluate the existing OpenDiscourse architecture from first principles while preserving validated data, source evidence, and proven ingestion assets.

Do not assume current project docs or existing Connector decisions are correct merely because they are documented.

The objective is to establish a stable foundation before expanding legislative, identity, finance, election, crime, and research domains.

## Primary problems

1. Current legislative canonical model is missing Post/seat and represented-area semantics.
2. Membership and identity provenance need stronger cross-source modeling.
3. Current 10-stage Connector protocol conflates provider behavior with runtime/orchestration behavior.
4. OpenStates internal FDW schema must not become the stable researcher contract.
5. Federal bills/votes/memberships require a combined GovInfo + Congress.gov + official chamber + established community-tool strategy.
6. Current source roadmap unnecessarily blocks independent datasets behind congressional identity.
7. SQLModel/SQLAlchemy/psycopg overlap should be simplified.
8. PostgreSQL COPY and extensions/features should be used more deliberately.
9. CI still runs more DB work than necessary on every PR.
10. Market/security models should migrate out of OpenDiscourse to the CFA project.

## Constraints

Preserve:

- validated source artifacts,
- checksums/provenance,
- loaded Census/OpenStates/economic data,
- Git history,
- working CLI behavior where practical,
- Alembic migration history,
- existing research reproducibility.

Do not perform a destructive big-bang rewrite.

## Architecture direction

Use a strangler migration within the existing repository.

Bulk historical data + incremental APIs + immutable evidence + source-shaped stage + normalized canonical model + dbt marts + read-only access surfaces.

Use Open Civic Data/OpenStates/Popolo as the legislative interoperability baseline, extended where necessary.

## Required design decisions

BMAD architecture must explicitly decide:

- post/division/membership model,
- organization hierarchy,
- vote model,
- bill universal identity,
- sponsorship model,
- document manifestations,
- source assertion/provenance model,
- identity exception/resolution model,
- Connector v2 types and runtime responsibilities,
- source registry,
- SQLAlchemy/psycopg boundary,
- OpenStates canonicalization plan,
- federal source responsibility matrix,
- migration/parity strategy.

## First implementation target

After architecture approval:

1. improve CI/selective tests,
2. implement legislative primitives,
3. implement Connector v2,
4. migrate FRED as reference,
5. load congress-legislators,
6. implement federal legislative spine,
7. materialize OpenStates canonical data.

## Definition of success

The new foundation must demonstrate:

- simpler source adapter implementation,
- stable source-independent canonical entities,
- full evidence traceability,
- restart/idempotency,
- source reconciliation,
- no researcher dependency on upstream internal schemas,
- fast normal CI,
- clear deletion path for legacy architecture.

---

# 73. Prompt for Codex/Grok independent review

Use this if you want another agent to pressure-test the conclusions:

```text
Review the OpenDiscourse repository from scratch as a skeptical principal data
architect and senior Python/PostgreSQL engineer.

Do not assume the current architecture, BMAD artifacts, AGENTS.md, previous
decisions, or this proposed review are correct.

The product goal is a self-hostable, provenance-aware public-policy and
social-science research warehouse combining authoritative U.S. government data
across legislation, people/memberships, votes, geography, demographics,
economics, elections, campaign finance, disclosures, crime, spending, and
documents.

Evaluate:

1. whether a restart, in-place refactor, or strangler-style v2 migration is best;
2. the canonical legislative model against Open Civic Data/OpenStates/Popolo;
3. GovInfo/Congress.gov/OpenStates/House/Senate acquisition architecture;
4. whether bulk history + API incremental is optimal per source;
5. mature Python libraries/projects we should wrap rather than rewrite;
6. PostgreSQL features/extensions that replace custom code;
7. SQLAlchemy/SQLModel/psycopg boundaries;
8. provenance, temporal identity, geography, and data-vintage modeling;
9. Connector/runtime abstraction quality;
10. CI/test performance and coverage strategy;
11. BMAD/TEA project plan and dependency ordering;
12. which existing code/tables should be retained, migrated, or deleted.

For every material recommendation, point to repository evidence or an external
authoritative/mature implementation.

Prefer simpler solutions and existing maintained projects.

Do not optimize for preserving existing code. Also do not recommend rewriting
working code without a measurable architectural benefit.

Return concrete schema changes, package boundaries, source responsibility
matrix, migration sequence, tests, and acceptance criteria.
```

---

# 74. Final recommendation

OpenDiscourse should **not** become a giant pile of scrapers.

It should become a **government/public-research integration platform**.

That distinction changes how the engineering should work.

Bad framing:

```text
Write a Congress scraper.
Write a Census scraper.
Write a FRED scraper.
Write a BLS scraper.
Write another parser.
```

Better framing:

```text
Acquire authoritative data using the strongest existing mechanism.
Preserve the evidence.
Normalize only the reusable research concepts.
Resolve identities explicitly.
Keep temporal/geographic semantics.
Build research-ready marts.
Expose boring, stable interfaces.
```

That is the valuable product.

The strongest pieces of the current repository already point in this direction.

The next step is not a total rewrite.

The next step is a **deliberate v2 foundation pass before the architecture gets more expensive to change**.

---

# Evidence reviewed

## Current OpenDiscourse repository

Reviewed current main branch areas including:

- `README.md`
- `AGENTS.md`
- `pyproject.toml`
- `.github/workflows/`
- `scripts/ci/`
- `src/opendiscourse_research/models/`
- `src/opendiscourse_research/ingestion/`
- `src/opendiscourse_research/providers/`
- `src/opendiscourse_research/db.py`
- `inventory/sources.yaml`
- `inventory/progress.yaml`
- `docs/model.md`
- BMAD PRD, architecture spine, specifications, and epics.

## External projects and authoritative documentation reviewed

- Library of Congress `api.congress.gov`
- GovInfo bulk/API documentation
- OpenStates / Plural Open data documentation and monthly PostgreSQL dump
- OpenStates API v3
- `openstates/pyopenstates`
- `openstates/openstates-core`
- `unitedstates/congress`
- `unitedstates/congress-legislators`
- House/Senate official roll-call sources
- FBI Crime Data Explorer
- Census ACS Summary Files
- Census TIGER/Line
- DataMade `census`
- BLS QCEW bulk data
- U.S. BEA `beaapi`
- FRED/ALFRED API
- FEC bulk/OpenFEC
- USAspending API
- `usaspending-orm`
- MIT Election Data + Science Lab
- OpenElections
- PostgreSQL 17 documentation
- Psycopg 3 COPY/pipeline documentation
- pgvector
- BMAD brownfield/project-context guidance
- BMAD TEA testing/CI guidance.

---

# Immediate discussion questions

The architecture review leaves a few choices that are worth discussing before implementation:

1. Should the internal v2 work retain the package name `opendiscourse_research`, or eventually rename the Python package to simply `opendiscourse`?
2. Should political divisions be a separate `core.division` entity, or should we extend `core.geography` to represent both Census geography and OCD political divisions?
3. Should canonical source assertions use one generic provenance relation or domain-specific source-mapping tables?
4. How much federal government activity beyond legislation should be part of the first v2 target: hearings only, or also nominations/treaties/committee materials?
5. Do you want the current market tables migrated immediately to the CFA repository, or simply frozen/deprecated until CFA consumes them?
6. Should OpenStates incremental freshness use `pyopenstates` immediately, or should monthly bulk refresh be the only supported v2 mechanism until the canonical transform is complete?
7. Do you want the first implementation work to be the CI/test restructuring, or the legislative schema architecture/migrations?

My default answers are:

- keep the package name during migration,
- add a separate political `division` abstraction linked to geographic boundaries,
- start with explicit/domain source mappings before introducing a highly generic polymorphic provenance table,
- include hearings/committee meetings in design but not block v2 on nominations/treaties,
- deprecate market tables now and physically move them later,
- canonicalize the monthly OpenStates dump first, add API incremental second,
- and fix CI plus finalize the schema design before implementing large loaders.
