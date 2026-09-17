- source_spec: `_bmad-output/implementation-artifacts/spec-8-1-post-division-membership.md`
  summary: Null-OCD posts and divisions have only a UUID primary key; 8.2 loaders need an idempotency key for committee chairs without OCD ids.
  evidence: ADR-0002 wants unique keys for the same external identifier or artifact/member. Story 8.1 makes `ocd_id` / `ocd_division_id` optional. No loader in this story.

- source_spec: `_bmad-output/implementation-artifacts/spec-8-1-post-division-membership.md`
  summary: Live schema snapshot and operator warehouse still report Alembic head `c4f7a2d9e651` until `opendiscourse` on 5434 is upgraded and the snapshot regenerated.
  evidence: `docs/schema-snapshot/` is a live dump; tests used testcontainers. Do not treat the snapshot as the migration path.

- source_spec: `_bmad-output/implementation-artifacts/spec-8-2-openstates-promote.md`
  summary: Operator GRANT/IMPORT of `opencivicdata_division`, `opencivicdata_post`, and `opencivicdata_membership` into `openstates_source` is still required before `load-openstates-promote` can run against the live warehouse.
  evidence: Docs list the tables; this story does not change the dump or FDW server. Live snapshot still imports the older allow-list.

- source_spec: `_bmad-output/implementation-artifacts/spec-8-2-openstates-promote.md`
  summary: Regenerate `docs/schema-snapshot/` after 8.2 lands so catalog DDL shows `membership.ocd_id` and `identity_exception` kind `'membership'`.
  evidence: Snapshot is a review artifact, not the migration path. Alembic `b8c2f1d4e390` is the catalog change.

- source_spec: `_bmad-output/implementation-artifacts/spec-8-2-openstates-promote.md`
  summary: Duplicate OpenStates US session identifiers would abort set-based session upsert.
  evidence: Unverified dump uniqueness on `(jurisdiction_id, identifier)`. Settle by checking `opencivicdata_legislativesession` for duplicate US identifiers.

- source_spec: `_bmad-output/implementation-artifacts/spec-8-2-openstates-promote.md`
  summary: Unused `sql/query/legislation/unresolved_identity_exceptions.sql` and `congress_health.sql` still treat every identity_exception as a voter.
  evidence: Python health/report paths filter `kind = 'voter'`; these SQL files are not called at runtime.
