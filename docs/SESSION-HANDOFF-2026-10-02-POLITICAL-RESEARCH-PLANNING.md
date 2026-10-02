# Session handoff: political research planning complete (2026-10-02)

## Plain status

The FEC/OpenStates political-research **planning** programme is complete and
pushed to `main`. It is safe to start a new session. No data transfer, schema
migration, FDW change, broad OpenStates promotion, or FEC-to-person join has
been authorized or performed by this planning work.

## Read first in the next session

1. `AGENTS.md`
2. `docs/PROJECT-STATE.md`
3. `_bmad-output/planning-artifacts/political-research-programme-readiness-2026-10-02.md`
4. `_bmad-output/specs/spec-openstates-political-core/SPEC.md`
5. `_bmad-output/specs/spec-openstates-political-core/source-mapping.md`
6. `_bmad-output/specs/spec-fec-reproducible-ingest/SPEC.md`
7. `_bmad-output/specs/spec-fec-reproducible-ingest/stories.yaml`

## Completed planning commits

- `029b689` — political-research programme, FEC/OpenStates/mart specs, queue,
  and readiness record.
- `e1c12ef` — independent-review corrections for FDW scope, FEC coverage
  semantics, identity boundary, and mart grains.
- `fcca31b` — exact, strictly read-only Story 1 audit outputs.

All three are pushed to `origin/main`.

## Agreed architecture and safety rules

- OpenStates remains a separate, read-only provider snapshot. Its Django tables
  are never the OpenDiscourse researcher contract.
- OpenDiscourse uses OCD/Popolo concepts in owned normalized `core`/`fact`
  tables, preserving source identifiers and immutable evidence.
- FEC target is every available equivalent official family/cycle from
  2000–2024. A publisher-unavailable product is a documented coverage finding;
  a deferred or failed available product blocks a full-history completion claim.
- Federal people join through BioGuide. FEC candidates can join only through a
  reviewed, enabled stable-ID bridge. Committees and names never join directly
  to `core.person`.
- Research marts are dbt-owned, declare one exact row grain, show coverage
  status, and retain evidence drill-through. No opaque political score.

## Next work: Story 1 only

Story 1 is a **strictly read-only OpenStates evidence audit**. It must produce:

1. restored-snapshot inventory;
2. snapshot-versus-FDW coverage difference;
3. entity and field disposition matrices;
4. coverage report;
5. source fingerprint/drift baseline;
6. identifier/BioGuide audit; and
7. promotion reconciliation baseline.

It must not create a migration, alter the FDW, write the source database,
promote rows, transfer FEC files, or enable a person join. The full contract is
the `Required Story 1 audit outputs` section of `source-mapping.md`.

## Working-tree boundary

The workspace remains intentionally dirty with separate Congress/FEC
implementation work, contract/config changes, new database-skill files, and a
Congress 120 handoff. Preserve them. Do not stage, commit, revert, or test them
as part of Story 1 unless the operator explicitly changes scope.

## Verification already performed

- `research-db progress-check` passed.
- `stories.yaml` has six valid string IDs and every story has planning and
  completion checkpoints.
- `git diff --check` passed for each planning commit.

## GitHub tracking recommendation

Create one GitHub issue per queue story (Stories 1–6), with the corresponding
spec/companion paths and completion checklist in the issue body. Start only
Story 1. Do not create generic “FEC complete” or “OpenStates import” issues;
they are too broad to review or close safely.
