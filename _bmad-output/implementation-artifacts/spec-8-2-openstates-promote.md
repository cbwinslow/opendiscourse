---
title: 'Story 8.2 — OpenStates promote, not public FDW'
type: 'feature'
created: '2026-09-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '0aceff3bac3b248ded10635d5a2f26037ac43799'
context:
  - '{project-root}/.agents/skills/opendiscourse-schema-change/SKILL.md'
  - '{project-root}/.agents/skills/opendiscourse-provenance/SKILL.md'
  - '{project-root}/.agents/skills/opendiscourse-testing/SKILL.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Researchers still have to query `openstates_source.opencivicdata_*` for sessions and occupancy. `core.legislative_session` has two US rows from GovInfo; `core.membership` is empty; post/division exist but are unused. FDW is not the researcher contract (AD-8).

**Approach:** Promote a **federal-only** slice from the read-only FDW into owned `core`: US jurisdiction, US legislative sessions, then posts/divisions and memberships for people **already** in `core.person`. Dump stays replace-only. Re-run is idempotent.

## Boundaries & Constraints

**Always:** Read `openstates_source` only; never write database `openstates`. Bound: `ocd-jurisdiction/country:us/government` (same filter as `openstates_federal_people.sql`). Reuse `ensure_us_legislative_session` / existing upsert SQL; add set-based `sql/query/legislation/` promote statements. Register an `ingest.artifact` for the FDW snapshot (same pattern as `load_openstates_votes`). Provenance CHECK on new rows. Skip memberships with null FDW `person_id` or no matching `core.person_identifier` namespace `ocd` — record unresolved exceptions; never name-match `person_name`. Posts use dump `id` as `core.post.ocd_id`. Divisions use dump `id` as `ocd_division_id`; no `geography_id`. Additive Alembic: nullable unique `core.membership.ocd_id` (dump membership `id`) so chairs/null-OCD are not this story's idempotency key. CLI entry next to existing `load-openstates-*`; no `plans.py` HANDLERS elif; not a Connector (not a new source). Tests use an isolated source-schema stand-in, never a live dump restore.

**Never:** Copy Django dump tables into `core`. Promote all ~1.8k jurisdictions or ~91k memberships. Re-copy federal people/orgs/votes (already loaded). Backfill `bill.legislative_session_id` / change unique keys (8.3). Epic 4 vote scrapers. Connector v2. FRED. Epic 7. `btree_gist` occupancy. Parent-organization rewrite. `pyopenstates` API v3.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| US sessions | FDW sessions for US jurisdiction; two `core` sessions already exist | Upsert by `(jurisdiction_id, identifier)`; count grows to FDW US sessions; existing GovInfo rows keep ids | Missing artifact/payload → session CHECK fails |
| Occupancy | FDW membership with OCD person already in `core`, post with division | `core.post` / `core.division` / `core.membership` rows; `post_id` set | Unknown post org → skip/FK, no partial person-only insert |
| Null person | FDW membership `person_id` null, `person_name` present | No `core.membership`; unresolved exception | Must not join on display name |
| Idempotent rerun | Promote twice on same FDW snapshot | Same UUIDs; unique `ocd_id` holds | Duplicate membership `ocd_id` → unique violation swallowed by upsert |
| Non-US row | VA legislature session/membership in FDW | Not inserted | N/A |

**Decision (2026-09-17):** Grain is **US jurisdiction + sessions, then federal membership/post/division**, not “or”. All-state promote is a later story. 8.3 still waits until every bill/roll_call has `legislative_session_id`.

</frozen-after-approval>

## Code Map

- `sql/query/legislation/openstates_federal_people.sql` — bound filter to copy (`current_jurisdiction_id = 'ocd-jurisdiction/country:us/government'`).
- `sql/query/legislation/ensure_jurisdiction.sql`, `ensure_legislative_session.sql` — reuse upserts; FDW `start_date`/`end_date` map to `starts_on`/`ends_on`.
- `src/opendiscourse_research/repositories/legislation.py` — `ensure_us_legislative_session`, `sync_openstates_federal_*`; add promote functions; SQL-only.
- `src/opendiscourse_research/peopleload.py` + `cli.py` — existing OpenStates CLI; add one promote command, no new dispatcher family.
- `src/opendiscourse_research/openstatesstage.py` — isolated source-schema stand-in for tests (do not provision live FDW).
- `src/opendiscourse_research/models/core.py` — `core_membership` needs nullable unique `ocd_id` (Alembic; same partial unique as `core.post`).
- `docs/openstates-integration.md` — document the promote path; FDW remains not the researcher contract.
- Do not edit `sql/012_openstates_baseline.sql`, FRED, `plans.py` HANDLERS, or dump restore scripts.

## Tasks & Acceptance

**Execution:**
- [x] `migrations/versions/*_membership_ocd_id.py` -- nullable unique `membership.ocd_id` -- 8.1 deferred chair key; dump memberships have ids
- [x] `sql/query/legislation/openstates_promote_*.sql` -- set-based FDW → core for US jurisdiction/session/post/division/membership -- bound promote
- [x] `src/opendiscourse_research/repositories/legislation.py` -- promote entrypoints using those SQL files -- SQL-only
- [x] `src/opendiscourse_research/peopleload.py` / `cli.py` -- one command, provenance artifact, unresolved exceptions -- no HANDLERS elif
- [x] `tests/test_persistence_foundation.py` (or focused db test) -- stand-in FDW: upsert session, skip nameless membership, idempotent ocd_id -- 8.2 ACs
- [x] `docs/openstates-integration.md` -- researcher queries `core`, not FDW -- AD-8

**Acceptance Criteria:**
- Given US sessions in the FDW stand-in, when promote runs, then `core.legislative_session` contains those identifiers under `ocd-jurisdiction/country:us/government` and a second run does not duplicate.
- Given a federal FDW membership whose person OCD id is already in `core.person_identifier`, when promote runs, then a `core.membership` row exists with `post_id` set when the dump post exists.
- Given an FDW membership with only `person_name`, when promote runs, then no membership row is inserted and an unresolved identity exception is recorded.
- Given a non-US FDW jurisdiction/session, when promote runs, then those rows are absent from `core`.
- Given database `openstates`, when promote runs, then it is not written.

## Implementation Notes

Approved 2026-09-17 (approve-and-stop). Frozen intent is locked. Resume with `bmad-build` on this file; do not renegotiate grain.

## Design Notes

Promote is `INSERT … SELECT` from FDW into owned tables keyed by OCD ids. Federal people and organizations stay on the existing loaders; this story attaches seats and sessions to them. Committee posts without a division keep `division_id` null.

## Verification

**Commands:**
- `just check-fast` -- expected: pass
- `just check-db` -- expected: promote tests pass on stand-in schema
- `uv run alembic upgrade head` -- expected: membership `ocd_id` applies and downgrades

## Review Triage Log

- `false` — Blind: live FDW missing division/post/membership imports will make the CLI fail. Docs already list GRANT/IMPORT as administrator work; this story does not own the FDW server. The code reads `openstates_source` only.
- `false` — Blind: stand-in promote test skips whenever `openstates_source` exists, so promote never runs. `just check-db` used testcontainers without that schema; `test_openstates_federal_promote_uses_standin_fdw` PASSED (not skipped).
- `false` — Blind: year-only / `YYYY-MM` dump dates become NULL. `starts_on`/`end_date` are dates; partial ISO is not a date, so NULL is the mapping, not a dropped bound.
- `false` — Blind: membership exceptions are invisible in quality reports. They land in `ingest.identity_exception` and in `load-openstates-promote` counts; congressional reports stay voter-scoped so occupancy misses do not inflate voters.
- `false` — Blind: unknown org/post memberships are silent omits. Frozen matrix says skip/FK and no person-only insert; that is the implemented join.
- `low` — Blind: rerun test compares RETURNING counts, not UUIDs. `ON CONFLICT DO UPDATE` does not replace `membership_id`; unique `ocd_id` is covered by `test_membership_ocd_id_is_unique_when_present`.
- `false` — Blind: missing artifact/payload session CHECK is untested. `test_ensure_us_legislative_session_lineage_validation` already requires artifact or payload.
- `medium` — Blind/edge: Alembic downgrade restores `kind IN ('voter')` without deleting `kind = 'membership'` rows, so a data-bearing `downgrade -1` fails.
- `low` — Blind: `ensure_jurisdiction` then promote `DO NOTHING` double-writes US jurisdiction. Existing GovInfo row is kept; harm is a zero `jurisdictions` count, not wrong data.
- `false` — Blind: synthetic artifact lacks dump checksum. `load_openstates_votes` registers the same style of FDW snapshot artifact.
- `low` — Blind: `docs/schema-snapshot/opendiscourse.schema.sql` was not regenerated. Snapshot is a review artifact, not the migration path.
- `false` — Blind: substring tests would miss `INSERT` into `openstates_source`. Promote SQL only inserts `core.*` and `ingest.identity_exception`.
- `high` — Edge: two unmatched memberships sharing one `person_id` make `openstates_promote_unresolved_memberships.sql` insert two identical `(run_id, kind, namespace, external_id, reason)` rows; PostgreSQL aborts `ON CONFLICT DO UPDATE` that hits one row twice.
- `low` — Edge: invalid calendar `YYYY-MM-DD` (e.g. 2024-02-31) still matches the regex and `::date` errors. Real OCD dates are empty, partial, or valid; a safe cast needs a helper, not a wrap that still evaluates `::date`.
- `low` — Edge: same unguarded `::date` on membership occupancy dates.
- `maybe-false` — Edge: two US FDW sessions with the same `(jurisdiction_id, identifier)` would abort session upsert. Dump uniqueness is not proven here.
- `medium` — Verify-gap: `unresolved_congressional_identities` kind filter is untested; deleting it would still pass current tests and emit membership misses as voters.
- `medium` — Verify-gap: `congressional_health` `unresolved_voters` kind filter is untested the same way.
- `medium` — Verify-gap: nameless stand-in `person_name` is `'Name Only Member'`, so a `full_name` join would still skip it; the AC does not catch name-matching.
- `low` — Verify-gap other: unused `congress_health.sql` / `unresolved_identity_exceptions.sql` still sum exceptions without `kind = 'voter'`. Python does not call them.
