---
name: opendiscourse-rebuild
description: Guide a fresh OpenDiscourse checkout through safe configuration, database initialization, source readiness, and verification. Use for bootstrap, rebuild, portability, or "how do I ingest this source" requests; do not use to add a new source or alter warehouse schema.
---

# OpenDiscourse rebuild

Use this skill to make an existing OpenDiscourse workflow reproducible from a
fresh checkout. It is a guide to the project's commands and safeguards; it
does not replace a Connector, source contract, or operator approval for a
large download.

## Start with the real state

Read `AGENTS.md`, `docs/PROJECT-STATE.md`, and
`_bmad-output/specs/spec-rebuild-kit/SPEC.md` before suggesting a command.
Use `inventory/sources.yaml` for approved sources and `inventory/progress.yaml`
for their actual tracked state. A source that is catalogued, blocked, or only
partially loaded is not authorized for a new transfer.

For a source-specific request, also load its project skill when relevant:

- Connector: new source or source workflow boundary.
- Provenance: acquisition, artifacts, checksums, resume, or publication.
- Schema change: migrations or tables.
- Testing: test selection or verification.

## Safe bootstrap path

1. Keep configuration in the checkout's `.env`, derived from `.env.example`.
   Use Settings and documented variables such as `DATABASE_URL`, `DATA_ROOT`,
   and provider API-key variables. Never print, copy into a command, or commit
   a secret.
2. Follow `docs/getting-started.md` to choose Docker development or the
   documented bare-metal PostgreSQL path. Confirm the intended database before
   initialization: normal bare metal uses port 5434; Docker Compose uses 5433.
3. Use `uv run research-db init-db` to create/update schema and seed the
   catalog. It must not contact a provider.
4. Use read-only status/coverage commands and the source contract to decide
   whether a source is ready. Run `just check-fast` before calling a code or
   configuration change verified.

## Source ingestion boundary

Do not run a generic "ingest everything" command. Choose the source's
documented Connector or plan, then follow its sequence: discover, select,
capacity preview, explicit transfer approval, retain/inventory, stage,
validate, publish, and checkpoint. Preserve raw files; retries reuse verified
artifacts and do not overwrite evidence.

If a workflow is not implemented, has an unknown size, needs an unconfigured
API key, depends on a machine-specific legacy path, or has an identity gate,
stop and explain the blocker. Do not substitute a mirror, name-match people,
or create a local default outside `DATA_ROOT`.

## Current limits

The rebuild kit is still being built. `source-matrix.md` lists known gaps,
including tracked Census selections, OpenStates superuser setup, and the
unimplemented portable FEC downloader. Treat these as explicit blockers, not
steps to improvise around. FEC, elections, and disclosure person joins remain
gated by reviewed identifiers.

## Verification and handoff

Report the exact command, selected source scope, current phase, artifact/run
evidence, and any remaining publisher or configuration blocker. Use
`just check-fast` for normal code verification and `just check-db` only with a
test database or testcontainers; never point tests at the live warehouse.

Read `references/rebuild-matrix.md` when choosing a source workflow or deciding
whether an external plugin is ready to publish.
