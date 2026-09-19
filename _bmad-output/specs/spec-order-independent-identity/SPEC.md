---
id: SPEC-order-independent-identity
companions:
  - assertion-model.md
  - writers-and-stories.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Order-independent identity and shared-entity names

Rationale and rejected alternatives: `docs/adr/0005-source-assertions-and-deterministic-precedence.md` (accepted with changes, 2026-09-19).

## Why

A pain, found by the rebuild proofs (`docs/rebuild-proof-2026-09-19.md`). Two shared
entities depend on which loader runs first. Person identity does: OpenStates looks a
person up by its OCD id only, so loading legislators first (the rebuild kit's order)
creates up to about 722 duplicate people; live already holds one (Stutzman). Display
names do too: `core.person` names are first-writer-wins and `core.geography.name` has
three writers with three rules, so a better source can never correct an earlier value
and a rebuild differs from live (246 people). The operator will drop the `stage`
duplicates only after a rebuild is proven, and that proof needs identity and names to
be a pure function of the loaded sources. Identity must be fixed before names.

## Capabilities

- **CAP-1**
  - **intent:** A person is found by any known identifier (BioGuide, OCD, others in `core.person_identifier`), never by name, whichever loader sees it first.
  - **success:** An identity order test loads legislators and OpenStates in both orders on a scratch database and asserts identical person and identifier sets, with no person created for an OCD id whose BioGuide id is already owned.

- **CAP-2**
  - **intent:** An identifier set that names two existing persons, or sources that contradict each other, is never guessed at: the association aborts, a conflict record is written, and it stays visible in the conflict report.
  - **success:** A test that seeds two persons owning one asserted identifier set leaves both untouched, writes one conflict record, and reruns without a second record.

- **CAP-3**
  - **intent:** A reviewed duplicate person is merged into its survivor in one auditable transaction.
  - **success:** On a scratch copy the Stutzman exception in `inventory/identity_exceptions.yaml` merges (identifier attached, duplicate deleted, sponsorships, memberships, votes and identifiers repointed, colliding `fact.member_vote` rows kept in a merge-audit table), the run ledger records survivor, duplicate, per-table counts and collisions, and the file entry flips to `applied: true`; a rerun changes nothing.

- **CAP-4**
  - **intent:** Loaders record what each source says about an entity's name as typed assertions with evidence, and keep the losing values.
  - **success:** After loading, every person and geography row has at least one assertion carrying `dataset_id`, `source_vintage`, artifact or payload, and run; rerunning a loader adds no assertion and moves evidence in place.

- **CAP-5**
  - **intent:** Which source wins for each attribute is declared in tracked configuration and resolved deterministically.
  - **success:** Given the same assertions, resolution returns the same winner in any insertion order; a dataset that has assertions but no precedence row makes resolve fail with a message naming the dataset.

- **CAP-6**
  - **intent:** `core.person` and `core.geography` keep materialised names that only a resolver writes, each pointing to the assertion that won.
  - **success:** `research-db resolve` on a resolved warehouse reports zero changes; `--dry-run` writes nothing; a direct `UPDATE` of a resolved column by the application role is refused; every displayed name joins to an assertion through `name_source_id`.

- **CAP-7**
  - **intent:** The existing warehouse is brought onto assertions by rerunning the loaders, with the change known before it is applied and reversible in value.
  - **success:** On a scratch copy, `resolve --dry-run` after the loader rerun reports exactly the expected diff (246 person names; no geography name changes; full-name assertions added); a pre-image CSV of changed rows exists before apply; ranking OpenStates above legislators in `precedence.yaml` reproduces today's live names.

- **CAP-8**
  - **intent:** The rebuild kit's verify step compares resolved names with no exclusions.
  - **success:** Verify runs a final global `resolve --dry-run` that must report zero changes, and compares people and geography rows of the loaded datasets with live without listing known differences.

## Constraints

- Never match by name (ADR-0002). Federal person joins are BioGuide; any name assertion from FEC or disclosure data calls `identitygate.require_person_join` first.
- Every person creator and identifier writer takes the same advisory lock (precedent: `promote_legislators`). Today `sync_openstates_federal_people` and the Congress.gov upsert take none.
- The resolver is its own short transaction after the loader commits, under `pg_advisory_xact_lock(hashtextextended('resolve:<entity>', 0))`, updates non-key columns only in primary-key order, and writes only changed rows. Consistency is eventual by design: resolve is a pure function of the assertions committed when it runs.
- Enforcement of resolver-only writes is layered and honest: column `UPDATE` revoked from the application role, the resolver a narrowly owned function holding the privilege; a `BEFORE UPDATE` trigger with a `SET LOCAL` flag is an accidental-write guard, not security. Creating a row still inserts `full_name` (NOT NULL) and its assertion in one statement.
- Tie-breaks are rank, then `source_vintage` DESC, then natural key `COLLATE "C"`; never a uuid or database collation, never `ingest.current_artifact` (it orders versions of one artifact key; TIGER has 39 keys and 96 CBSA names differ across vintages). `name` resolves short then full so partial rebuilds never show NULL.
- Assertions come from loaders, never from `stage.*`: the kit drops about 37 GB of stage duplicates, including `tiger_feature`. The backfill is a loader rerun, done before any stage drop.
- Retained artifact files are never touched. Wiping and re-ingesting derived rows is authorized and recorded in the run ledger or `docs/PROJECT-STATE.md`.
- The migration is expand/contract and forward-only with a guarded downgrade; restore is the nightly dump plus the pre-image CSV. Schema by Alembic, set-based SQL in `sql/query/` (geography SQL now inline in `ingestion/*.py` moves there), no new `if/elif` in `cli.py`, `plans.py` or `registry.sync`; the precedence sync is keyed, not a branch.
- Any attribute two sources can describe for one entity gets an assertion table and precedence entry in the same change that adds the second source; the `opendiscourse-schema-change` and `opendiscourse-connector` skills say so.

## Non-goals

- No name matching, MDM or record-linkage library, and no generic entity-attribute-value table.
- No view replacing `core.person` or `core.geography` (foreign-key targets read by `dbt` and the fingerprint queries).
- No new data sources, scorecards, NLP or embeddings; no redesign of the Connector, run ledger or load strategies.
- No rebuild-kit work beyond its verify hook (CAP-8); no `stage` drops.
- No change to live data before the backfill story's expected diff is asserted on a scratch copy.

## Success signal

Loading the person and geography sources on an empty warehouse in any order gives
the same people, identifiers, resolved names and assertions, `research-db resolve
--dry-run` reports zero changes, every displayed name traces to the file or payload
that asserted it, and the live warehouse has one Marlin Stutzman.

## Assumptions

- Stutzman is the only OCD-only person in the warehouse. About 722 other OpenStates people already list a BioGuide id in `opencivicdata_personidentifier`, which the loader ignores; looking up by it is the fix. (Live counts were Fable-verified; the Codex review could not query the database.)
- Until the operator decides the open question below, the resolver's default reproduces today's live names.
- Delivery follows the story order in `writers-and-stories.md`; story 1 (identity) ships and merges alone.

## Open Questions

- **Operator:** does `core.person.full_name` show the common name ("Mike Lawler", mostly OpenStates) or the official one ("Michael Lawler", congress-legislators)? Recommendation: common, official kept and exposed beside it. Both are stored as assertions either way; it does not block story 1.
- One live person has no BioGuide id (1 of 12,771): is it the Stutzman duplicate? And 9,841 `person_identifier` rows have no artifact: should they gain evidence in the backfill, or stay as legacy rows?
