# Epic 8 Context: Legislative primitives (blocks Epic 4)

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Give `core` a seat/post and a political division that is not a Census GEOID, so membership can mean “this person occupied this office for this interval” before we load more votes or OpenStates rows. The OpenStates dump stays a replaceable snapshot; researchers query owned tables.

## Stories

- Story 8.1: Post, division, membership
- Story 8.2: OpenStates promote, not public FDW

## Requirements & Constraints

- Additive Alembic only. Existing membership rows stay valid (`post_id` nullable).
- Division is distinct from `core.geography` (Census). OCD language, not Django dump tables.
- Do not write into database `openstates`. Combine other sources in `core` by identifier.
- No Connector v2, no FRED work, no Epic 4 votes, no Epic 7 loaders.
- Provenance: new rows that represent source assertions still need artifact or payload evidence where the rest of `core` already requires it.
- Database `opendiscourse`. Bound parameters. JSONB via Jsonb.

## Technical Decisions

- Postgres is the system of record. Models in `src/opendiscourse_research/models/`; revisions in `migrations/versions/`.
- UUID primary keys plus optional `ocd_id`, matching bill/roll_call — not OpenStates dump PKs as ours.
- `btree_gist` occupancy exclusions are deferred until historical edge cases exist.
- Organization parent hierarchy is not this epic’s first story unless post cannot exist without it (post already points at organization).

## Cross-Story Dependencies

- 8.1 landed (PR #21, revision `a4f8c2e9b176`) and should stay ahead of 8.2 promote.
- 8.2 is a bounded **federal** promote from FDW (US sessions, then occupancy), not a dump merge and not all-state.
- Story 3.1 (BioGuide) can proceed in parallel; politician joins still wait on it.
