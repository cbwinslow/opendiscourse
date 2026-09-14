---
name: opendiscourse-provenance
description: 'Keep OpenDiscourse facts traceable to source evidence. Use when writing ingest, extract, stage, publish, checksum, capacity-gate, or artifact code, or when the user mentions ingest.run, resume, or provenance.'
---

# OpenDiscourse provenance

Read `AGENTS.md` and `_bmad-output/specs/spec-opendiscourse/SPEC.md` CAP-1.
Capacity gate fails closed on unknown size. Also load
`opendiscourse-testing` for ingest test cases.

## When to use

- Any load that creates or updates warehouse facts
- Checksums, raw lake writes, `ingest.run` rows
- Resume / checkpoint behavior on long jobs

## Do

- Every fact must resolve to `ingest.run` + URL + checksum.
- Use `IngestionRun` in `src/opendiscourse_research/ingestion/base.py`
  (`store_payload` SHA-256 on canonical JSON → `ingest.raw_payload` /
  `ingest.artifact`). Lake rules: `docs/lake.md`.
- Unknown size: `opendiscourse_research.capacity.storage_preview` — non-zero
  exit, not a guess.
- Raw evidence is immutable. Stage is the only auto-evolved layer.
- Long work uses `opendiscourse_research.feedback` (spinner or progress bar,
  phase, resume, actionable failure) — not ad-hoc prints.

## Do not

- Publish to `core`/`fact` without evidence.
- Treat `IngestionRun` as a Connector (see `opendiscourse-connector`).
- Bypass the capacity gate.
- Commit secrets or `.env`.
