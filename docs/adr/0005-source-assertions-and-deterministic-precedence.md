# ADR-0005: Shared-entity identity and attributes are order-independent (source assertions, deterministic precedence)

- Status: Accepted with changes (2026-09-19). Two independent reviews: Fable 5.1 (read-only, against code and live data) and Codex (accept with changes, code only; its sandbox could not query the database, so live counts are Fable-verified).
- Date: 2026-09-19
- Spine: AD-3 (provenance), AD-8; ADR-0002 (identity, provenance, ownership)
- Evidence: `docs/rebuild-proof-2026-09-19.md`; the loader code cited below; live queries recorded in the review

## Context

Rebuilding Congress 108 and population estimates from raw files reproduced every fact exactly, but two
shared entities did not come out the same as live: people (246 differ) and geography names. Reading the
writers shows design defects, not bad luck. There are two problems, and identity must be fixed first.

### Problem A: person identity depends on load order

- `upsert_person_by_ocd.sql` (OpenStates) looks a person up by its OCD id only; `upsert_person_by_bioguide.sql`
  and the legislators load look up by BioGuide only. If legislators load first (the kit's order), OpenStates creates
  up to about 722 duplicate people (one per OCD id it does not already own); BioGuide conflicts are only counted (`repositories/legislation.py:513-518`).
- Live already holds one such pair: Marlin Stutzman, `67e9e162…` (BioGuide S001188 and 15 other ids) and
  `b8b58549…` (OCD id only), and one person without a BioGuide id.
- `sync_openstates_federal_people` takes no advisory lock, unlike `promote_legislators`; the Congress.gov path
  (`ingestion/congress.py:96` to `legislation.py:571`) is a third, unlocked creator.

### Problem B: display attributes depend on load order

| Entity column | Writers | Effective rule |
|---|---|---|
| `core.person.full_name`, `given_name`, `family_name`, `metadata` | legislators, OpenStates, Congress.gov | **first writer wins**, never updated (live: 12,045 legislators-first, 723 OpenStates-first, 3 other; `metadata.canonical_baseline` differs by the same split) |
| `core.geography.name` | three writers: TIGER (`tiger_load.py:141-145`, overwrite), PEP (`pep_load.py`, first non-null), **ACS API `ingestion/census.py:50-62` (overwrite, "Autauga County, Alabama")**. ACS bulk, DHC and CBP create the row and fill FIPS but write no name | three writers, three rules |
| `core.geography.state_fips`, `county_fips` | TIGER overwrite; PEP and CBP `COALESCE`; ACS bulk and DHC `DO NOTHING` | same values today; still three rules |

Consequences seen: a more authoritative source cannot correct an earlier value; 11,379 long-form geoid rows
(`0500000US01001`, ACS and DHC) have no name; 9,841 `person_identifier` rows have no artifact. The geography
loaders keep inline SQL under `ingestion/*.py`, not `sql/query/`.

What the data really shows: live county (3,244) and state (56) names already equal the TIGER short `NAME`; the
"3,141 counties differ" was a PEP-only rebuild ("Autauga County" from `CTYNAME`) compared with live, not a change
to live. Live people that a correct resolver would change: **246** = 245 OpenStates-first + 1 Congress.gov
(`G000608`); by column 217 `full_name`, 103 `given_name`, 7 `family_name`. The change swaps common names for official
ones ("Mike Lawler" to "Michael Lawler"; a given name "Scott" to "C."), so official versus common must be explicit.

## Decision

### 1. Identity first (a prerequisite story)

- A person is found by **any known identifier** (BioGuide, OCD, others in `person_identifier`), never by name
  (ADR-0002 unchanged). An OCD-only record merges into the BioGuide person when both identifiers are asserted by
  sources; contradictory assertions stay unresolved and visible (existing conflict report), not silently split.
- Every person creator and identifier writer takes the same advisory lock (precedent: `repositories/people.py`).
- "Any known identifier" must resolve to **exactly one** person. If two existing persons own the identifiers, the
  association is aborted and a conflict record is written (never guessed).
- A duplicate merge is one transaction under the person lock: repoint `core.person_identifier`, `core.bill_sponsorship`,
  `core.membership` and `fact.member_vote` (`models/core.py` lines 198, 261, 647, 732) from the duplicate to the survivor;
  where `fact.member_vote` collides on `(roll_call_id, person_id)` the losing row is preserved in a merge-audit table
  before deletion; then delete the duplicate. The transaction records survivor, duplicate, every repointed row count and
  every collision in the run ledger, and is rehearsed on a scratch copy first.
- An **identity order test** loads legislators and OpenStates in both orders and asserts the same person and
  identifier sets.

### 2. Source assertions for shared attributes

Loaders write typed *assertions*, not resolved values: `core.person_name_source` and `core.geography_name_source`.
Each row carries: entity id; `name_kind` (`official`, `common` for people; `short`, `full` for geography);
the value(s) exactly as given (a person's full/given/family triple travels together from one assertion);
`dataset_id` (FK to `catalog.dataset`); `source_vintage` (release year or period); evidence as **artifact OR payload,
plus run** (ADR-0002 rule 3; OpenStates and Congress.gov members have no artifact, so artifact is nullable);
and a natural-key unique index `NULLS NOT DISTINCT` so reruns are idempotent and evidence moves in place
(pattern: `upsert_term_memberships.sql`). ZCTA name assertions are skipped (the name equals the geoid).
Creating a `core.person` still inserts an initial `full_name` (NOT NULL) and its assertion in one statement;
after that only the resolver updates the column.

### 3. Deterministic precedence

`inventory/precedence.yaml`, synced into `catalog.attribute_precedence` (a keyed sync, not a `registry.sync`
branch), lists per entity, per attribute, per `geography_type`, the ordered sources **and the field each maps to**.
Resolution: highest-ranked source with an assertion; then `source_vintage` DESC; then the natural key with
`COLLATE "C"` (never a uuid, never database collation). It does not use `ingest.current_artifact` for tie-breaks:
that view orders versions of one artifact key only, but TIGER has 39 keys (one per vintage) and 96 CBSA names differ
across vintages. `name` resolves as short, falling back to full, so partial rebuilds never show NULL. A dataset that
has assertions but no precedence row **fails closed**.

Initial precedence:
- person `official` name: `congress.legislators` > `congress.legislation` (Congress.gov members) > `openstates.legislation`.
  The display column keeps today's semantics through an explicit `name_kind` choice recorded in the file.
- geography short name: `census.tiger` `NAME`; for PEP counties the field is `CTYNAME` (PEP has no `NAME`; `STNAME` is the
  state), so PEP supplies `full`, not `short`. Geography full name: TIGER `NAMELSAD` (county and CBSA only; the loader must
  start reading it) > PEP `CTYNAME` > ACS `NAME`.
- The mapping is per `geography_type`, not one rule.

### 4. Resolved columns, winner pointer, one writer

`core.person.full_name/given_name/family_name` and `core.geography.name` stay as materialised results, plus a
`name_source_id` FK to the winning assertion, so "every displayed name is traceable" is a join-free fact and verify is a
comparison. Only the resolver updates them. Enforcement is layered and honest about its limits: the application role
has column-level `UPDATE` revoked on the resolved columns, and the resolver is a narrowly owned function that holds the
privilege; a `BEFORE UPDATE` trigger with a `SET LOCAL` flag is only an accidental-write guard (any SQL-capable role can
set a custom setting, and an `UPDATE` trigger does not cover inserts, which the creation rule below covers). `state_fips`/`county_fips` come from one shared
derivation from the geoid, not five write rules. A view was rejected: `core.person` and `core.geography` are foreign-key
targets and are read by `dbt` and the fingerprint queries; with 12.8K people and about 50K geographies cost is not a factor.

### 5. Resolver: concurrency and cost

The resolver runs as its own short transaction after the loader commits (not inside it), under
`pg_advisory_xact_lock(hashtextextended('resolve:<entity>', 0))`, ordering updates by primary key, writing only rows whose
result changed and reporting them from `RETURNING`. It updates non-key columns only, so it does not block foreign-key
inserts. `research-db resolve [--dry-run]` reruns it. The resolver's lock serializes resolvers only, not concurrently
committed assertion inserts, so consistency is **eventual by design**: a resolve is a pure function of the assertions
committed when it runs, each loader resolves after its own commit, and the rebuild kit's verify step runs one final global
`resolve --dry-run` that must report zero changes.

### 6. Tests

Identity order test (Decision 1); name order-independence (all load orders give equal resolved rows and assertion sets);
resolver idempotency; a concurrent-resolver test; the trigger guard; the fail-closed rule.

### 7. Backfill and rollback

Do not source assertions from `stage.*`: the rebuild kit drops the roughly 37 GB stage duplicates, including
`tiger_feature`. Make each loader write assertions idempotently and **rerun the loaders as the backfill**, before any
stage drop. Save a pre-image CSV of changed rows, run `resolve --dry-run`, assert the expected diff (the 246 people; no
geography name changes; `full_name` added), then apply and record it in the run ledger and `PROJECT-STATE.md`. Rollback is
a precedence flip: ranking OpenStates above legislators reproduces today's live names. That restores *values*, not the
old schema or old-loader compatibility: the migration is expand/contract and forward-only, with a guarded downgrade and a
documented restore from the nightly dump plus the pre-image CSV. The expected diff is 246 person names and the addition
of full-name assertions (`core.person.full_name` already exists and is NOT NULL); no geography name changes.

### 8. Rule for the future

Any attribute two sources can describe for one entity gets an assertion table and precedence entry in the same change
that adds the second source. `opendiscourse-schema-change` and `opendiscourse-connector` say so. Any name assertion from
FEC or disclosure data must call `identitygate.require_person_join` first.

## Open decision (operator)

Which name kind feeds `core.person.full_name`: **common** (what people search and read, "Mike Lawler", mostly
from OpenStates) or **official** (the legal name, "Michael Lawler", from congress-legislators)? Both are stored as
assertions either way. Recommendation: `full_name` = common, with the official name kept and exposed beside it; the
precedence file then ranks OpenStates above legislators for `common` and legislators first for `official`. Until
decided, the resolver's default reproduces today's live names.

## Consequences

- Two rebuilds give the same identity and display values in any load order; a better source added later wins on the next resolve.
- Losing values are kept, and every displayed name points at the artifact or payload that asserted it.
- Cost: two assertion tables, a precedence table and file, a resolver, a trigger, an identity fix, loader edits (three geography
  name writers, six geography row writers for FIPS, three person writers), a duplicate-merge, and a backfill. This is an M-to-L change; it precedes the rebuild kit's
  verify step, which can then compare resolved values with no exclusions.
- The kit's verify step compares only the datasets actually loaded.

## Alternatives rejected

- Fix the load order: fragile, stores no evidence for losing values.
- First-writer or last-writer wins: a poorer source can block or overwrite a better one.
- A view instead of columns: forces base-table renames; see Decision 4.
- A generic entity-attribute-value table: weak typing and constraints.
- An MDM or record-linkage library: the problem is survivorship for already-keyed entities; matching stays identifier-based.
- Tie-break by uuid or database collation: reintroduces environment dependence.

## Follow-up

Change class M/L: `bmad-spec`, then stories in this order: (1) identity fix, lock and duplicate merge; (2) assertion tables,
precedence file and sync, resolver, trigger, tests; (3) geography loaders, including the ACS writer; (4) person loaders;
(5) backfill on a scratch copy, then live; (6) rebuild kit verify.
