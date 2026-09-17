---
title: 'Story 8.1 — Post, division, membership'
type: 'feature'
created: '2026-09-17'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '7e70038c2bca4d60a0e5170b558bbede93e4dd1f'
context:
  - '{project-root}/.agents/skills/opendiscourse-schema-change/SKILL.md'
  - '{project-root}/.agents/skills/opendiscourse-testing/SKILL.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `core.membership` is person → organization. That cannot represent “VA-06 for 2019–2023” or “Senate Class 1,” so votes and OpenStates promote would freeze the wrong grain.

**Approach:** Add owned `core.division` and `core.post`, and a nullable `membership.post_id`. Existing rows stay valid. No dump writes, no vote loaders, no org-hierarchy rewrite.

## Boundaries & Constraints

**Always:** Alembic revision (reversible). UUID PKs plus optional unique `ocd_id` / `ocd_division_id`. Division ≠ `core.geography`. `post.organization_id` required; `post.division_id` nullable (committee chairs have no district). `membership.post_id` nullable. 8.1 stores division **identifiers only** (label, classification, validity dates). No `geography_id` on division. Spatial join is a later `division`↔`geography_boundary` table when TIGER vintages are attached. Provenance on post/division matches other `core` entities that require artifact or payload. Tests: add, null post_id still legal, FK reject on bad post, division without a Census row.

**Never:** Copy OpenStates Django tables. Put a Census `geography_id` on `core.division` (that collapses redistricting history onto one polygon). `btree_gist` occupancy exclusions. Loader/promote (8.2). Connector v2. Parent-organization column. Destructive rewrite of membership. Empty junction table with no rows in this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Empty membership | Existing person+org membership, `post_id` null | Still inserts and reads | N/A |
| Seat occupancy | Post for an org + optional division; membership with `post_id` | FK holds; query by post | Invalid `post_id` → FK error |
| OCD id | Two posts with same `ocd_id` | Second insert fails unique | Unique violation |
| Division vs GEOID | Division with `ocd_division_id`, no Census geoid required | Row stored | Must not require `core.geography` |

**Decision (2026-09-17):** Division ↔ TIGER is **A now, C later, never B.** OCDEP 2 defines a Division as a political identity that may have many boundaries over its life, and explicitly does not specify boundary storage. OpenStates Post has `division_id` (ocd-division/…/cd:2), not a shapefile. Census CD GEOIDs are vintage/congress-variant; `ocd-division-ids` already has `census_geoid` + `validThrough` (CA-53 obsolete 2023-01-03). Putting `geography_id` on division is the bug this epic exists to avoid.

</frozen-after-approval>

## Code Map

- `src/opendiscourse_research/models/core.py` — `core_geography` (Census, keep), `core_organization` (no parent today), `core_membership` (add nullable `post_id`). Add `core_division`, `core_post`, accessors.
- `src/opendiscourse_research/models/__init__.py` — export new table helpers.
- `migrations/versions/` — new revision; discover head with `alembic heads` (graph is not a single line). Follow `migrations/versions/b9e3a6d4f182_adopt_canonical_memberships.py` style.
- `migrations/baseline/` + `scripts/render_baseline_ddl.py --check` if that gate still expects baseline drift — do **not** hand-edit baseline; Alembic-only.
- `tests/test_persistence_foundation.py` — already lists `core.membership`; extend for new relations and null `post_id`.
- Do not edit `sql/012_openstates_baseline.sql` as the live path; bootstrap SQL is legacy reference.
- Do not touch `registry.py`, FRED, or `openstates` dump.

## Tasks & Acceptance

**Execution:**
- [x] `src/opendiscourse_research/models/core.py` -- add division + post tables; nullable `membership.post_id` -- owned OCD grain
- [x] `migrations/versions/*_legislative_posts_and_divisions.py` -- Alembic upgrade/downgrade -- reversible contract
- [x] `tests/test_persistence_foundation.py` (and/or a focused db test) -- null post, FK, unique ocd_id -- 8.1 ACs

**Acceptance Criteria:**
- Given an existing membership with no post, when the revision runs, then the row remains valid.
- Given a post tied to an organization and optional division, when a membership references it, then the FK succeeds.
- Given two posts with the same non-null `ocd_id`, when the second is inserted, then the unique index rejects it.
- Given a division, when no Census geography row exists, then the division still stores.

## Implementation Notes

## Design Notes

Post is a seat in an organization (House district, Senate class, committee chair). Membership is occupancy over `[start_date, end_date]`. Division is the political area the post represents, identified in OCD terms, not a TIGER vintage.

## Verification

**Commands:**
- `uv run alembic heads` / upgrade on test DB -- expected: revision applies and downgrades
- `just check-fast` -- expected: pass (no db)
- `just check-db` -- expected: new persistence tests pass (needs test DB or testcontainers)

## Review Triage Log

| Finding | Verdict | Evidence / route |
|---|---|---|
| membership.post_id can reference a post on a different organization | medium | Real: FK is post_id only. Occupancy of a post has one reading (that org). Route: patch — composite unique+FK. |
| No test that duplicate `ocd_division_id` is rejected | medium | Unique partial index exists; only posts are tested. Route: patch — mirror post unique test. |
| division_check / post_check untested | medium | CHECKs exist; no IntegrityError insert. Route: patch — provenance failure tests. |
| AC “when the revision runs” not an upgrade-path test | medium | `test_membership_without_post_remains_valid` inserts at head. Route: patch — insert at `c4f7a2d9e651`, upgrade, assert null post_id. |
| Upgrade inspect-and-skip vs downgrade always-drop | medium | Tables are not in baseline; skip can leave indexes/FKs missing and make downgrade drop foreign objects. Route: patch — always create/drop. |
| Schema inspect omits post NOT NULL, nullable division_id, unique indexes, CHECKs | low | Extra asserts, everyday developers hit this. Route: patch. |
| Occupied post `division_id` not read back | low | Fixture writes it; only chair null is asserted. Route: patch. |
| Downgrade+reupgrade only checks alembic_version | low | After destructive downgrade, tables should be asserted present. Route: patch. |
| Inspect `get_columns("membership")` if membership missing | false | Membership is created by earlier revisions; greenfield never reaches this revision without it. |
| `valid_from` > `valid_to` allowed | low | Real but not in frozen matrix; extra CHECK is more than a direct correction. Reject. |
| VA-06 fixture uses valid_from/valid_to on identity | false | Spec requires validity dates on division; fixture is example data, not a second identity. |
| Null-OCD posts have only UUID PK | defer | Spec makes OCD ids optional; 8.2 loaders own idempotency for chairs. |
| Docs/snapshot still name head `c4f7a2d9e651` | defer | Operator snapshot is live-cluster; regenerate after warehouse upgrade. |
| schema-invariants class A omits new tables | low | Companion drift. Route: patch — add division/post to class A. |
