---
title: 'Story 8.2 — OpenStates promote, not public FDW'
type: 'feature'
created: '2026-09-17'
status: 'ready-for-dev'
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
- [ ] `migrations/versions/*_membership_ocd_id.py` -- nullable unique `membership.ocd_id` -- 8.1 deferred chair key; dump memberships have ids
- [ ] `sql/query/legislation/openstates_promote_*.sql` -- set-based FDW → core for US jurisdiction/session/post/division/membership -- bound promote
- [ ] `src/opendiscourse_research/repositories/legislation.py` -- promote entrypoints using those SQL files -- SQL-only
- [ ] `src/opendiscourse_research/peopleload.py` / `cli.py` -- one command, provenance artifact, unresolved exceptions -- no HANDLERS elif
- [ ] `tests/test_persistence_foundation.py` (or focused db test) -- stand-in FDW: upsert session, skip nameless membership, idempotent ocd_id -- 8.2 ACs
- [ ] `docs/openstates-integration.md` -- researcher queries `core`, not FDW -- AD-8

**Acceptance Criteria:**
- Given US sessions in the FDW stand-in, when promote runs, then `core.legislative_session` contains those identifiers under `ocd-jurisdiction/country:us/government` and a second run does not duplicate.
- Given a federal FDW membership whose person OCD id is already in `core.person_identifier`, when promote runs, then a `core.membership` row exists with `post_id` set when the dump post exists.
- Given an FDW membership with only `person_name`, when promote runs, then no membership row is inserted and an unresolved identity exception is recorded.
- Given a non-US FDW jurisdiction/session, when promote runs, then those rows are absent from `core`.
- Given database `openstates`, when promote runs, then it is not written.

## Implementation Notes

## Design Notes

Promote is `INSERT … SELECT` from FDW into owned tables keyed by OCD ids. Federal people and organizations stay on the existing loaders; this story attaches seats and sessions to them. Committee posts without a division keep `division_id` null.

## Verification

**Commands:**
- `just check-fast` -- expected: pass
- `just check-db` -- expected: promote tests pass on stand-in schema
- `uv run alembic upgrade head` -- expected: membership `ocd_id` applies and downgrades
