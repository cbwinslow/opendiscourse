# Session handoff: ACS archive audit and run ledger

**Date:** 2026-09-29 UTC

Read this file first, then `docs/PROJECT-STATE.md`, `AGENTS.md`, and the
implementation spec named below. Code and test output override this handoff.

## Active archive service: do not interfere

`od-acs-housing-archive.service` is the only approved managed ACS/AHS archive
worker. Do **not** start a second worker, restart it, or alter its live process.
It had no service-journal error signal when last checked and was actively staging
PUMS data. Its retained evidence is complete: 3,762 usable official artifacts,
136,873,504,564 retained bytes, with no current failed artifact.

Read-only checks:

```sh
systemctl --user show od-acs-housing-archive.service \
  --property=ActiveState,SubState,Result,ExecMainCode,ExecMainStatus --no-pager
uv run research-db source-status census.acs_housing_archive
```

Do not clear browser cache. Browser cache is unrelated to server-side Census
transfer, parsing, or PostgreSQL staging.

## Completed audit and planning

The focused ACS/AHS audit is committed:

- `128a4db docs: audit ACS archive ingestion`
- `6a11471 docs: record ACS ingestion audit`
- `c6f5fcf docs: harden housing archive contract`

Key documents:

- `docs/research/2026-09-29-acs-schema-and-ingestion-audit.md`
- `_bmad-output/specs/spec-housing-microdata-archive/SPEC.md`
- `_bmad-output/specs/spec-housing-microdata-archive/product-and-field-policy.md`

Confirmed strengths: raw source rows are retained in source-shaped stage tables;
stage keys are artifact/member/ordinal; live checks found zero invalid indexes,
zero unvalidated constraints, zero duplicate ACS stage keys, zero raw-less stage
rows, and zero missing checksum/path values among current artifacts.

Confirmed gaps: the old archive path did not create a full run ledger, did not
reconcile each CSV member, had no dictionary definitions loaded yet, inserted
rows one at a time, and had incomplete AHS end-to-end test coverage. Raw
retention prevents field loss, but does not by itself document field meaning.

## In-progress feature: run ledger and member reconciliation

The operator approved implementation. Its authoritative build spec is:

`_bmad-output/implementation-artifacts/spec-acs-archive-run-ledger-reconciliation.md`

Status in its frontmatter is `in-progress`; baseline commit is
`c6f5fcf0ff36d30db348a214b609b4e589d93bbf`.

Uncommitted implementation changes currently exist in:

- `src/opendiscourse_research/ingestion/base.py`
- `src/opendiscourse_research/ingestion/connector.py`
- `src/opendiscourse_research/ingestion/acs_archive.py`
- `src/opendiscourse_research/models/ingest.py`
- `src/opendiscourse_research/repositories/source_status.py`
- `migrations/versions/f8a3c1d7e245_acs_member_reconciliation.py`
- `tests/test_acs_archive.py`
- the ignored implementation spec above (it may not appear in `git status`)

Intended behavior:

- connector-owned `IngestionRun` records code version, manifest, selected
  artifacts, checkpoint, terminal status, and total observed rows;
- per-member `ingest.run_target` rows record parsed, inserted, existing, and
  rejected counts under stable `artifact=<uuid>;member=<name>` coverage keys;
- unsafe ZIP paths, duplicate/empty headers, malformed rows, non-CSV inputs,
  and no-member artifacts fail before publication;
- releases cannot publish until every selected member reconciles;
- `research-db source-status census.acs_housing_archive` exposes latest-run
  reconciliation and distinguishes a failed/partial current run from historic
  failed artifact attempts.

Important review notes:

- The migration adds `rows_parsed`, `rows_existing`, and `rows_rejected` to
  `ingest.run_target`; downgrade refuses to discard nonzero reconciliation
  evidence. Review its Alembic ordering against the real revision chain before
  committing.
- The implementation has fast tests for duplicate headers and unsafe ZIP paths,
  but it still needs dedicated database-backed AHS stage-to-publish and
  interruption/resume coverage before completion.
- The current change does **not** solve the later batch/COPY performance work,
  dictionary import, projection geography/type fixes, or query-driven indexes.
  Those are separate follow-up slices in the audit.

## Verification state

Passed:

```sh
uv run pytest tests/test_acs_archive.py -q  # 39 passed
just check-fast                             # 639 passed
git diff --check                            # passed before the final DB run
```

One clean `just check-db` run is still attached to terminal session `19780`.
At handoff it had reached roughly 45%. It reported failures in
`tests/test_bill_text_connector.py` and `tests/test_house_votes_connector.py`,
which are outside the changed ACS files, but they are **not yet proven
pre-existing**. Do not label the database gate passed or unrelated until its
final output is captured and the failures are reproduced/triaged.

Earlier duplicate database-test runs were terminated because DB tests must not
run concurrently. Only the single session above should be allowed to finish.
To poll it from this context if available:

```python
tools.write_stdin({"session_id": 19780, "chars": "", "yield_time_ms": 60000})
```

If that terminal session is unavailable after resume, ensure no test process is
running, then run exactly one foreground `just check-db` and retain its complete
output. Do not use xdist for DB tests.

## Safe resume order

1. Let the one database test session finish or capture its final result.
2. Read the full implementation spec and inspect the diff from its baseline.
3. Add/finish the missing AHS and interruption/resume database tests; fix any
  test-discovered defect.
4. Run `just check-fast`, then one `just check-db`; only then perform the
  required build review and mark the spec done.
5. Commit the feature only after verification. Do not include the active
  archive's derived data or modify the active service.

