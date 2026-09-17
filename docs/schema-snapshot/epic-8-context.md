# Epic 8 Context: Legislative primitives (blocks Epic 4)

Copy of `_bmad-output/implementation-artifacts/epic-8-context.md` for
GitHub/ChatGPT review. That directory is gitignored as a BMAD
implementation artifact.

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

- 8.1 blocks Epic 4 (votes) and should land before 8.2 promote.
- 8.2 is a bounded promote from FDW, not a dump merge.
- Story 3.1 (BioGuide) can proceed in parallel; politician joins still wait on it.
