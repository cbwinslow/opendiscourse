---
id: SPEC-fec-reproducible-ingest
companions:
  - reuse.md
  - coverage-and-grains.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Reproducible FEC campaign-finance ingestion

## Why

OpenDiscourse needs usable, reproducible campaign-finance evidence from 2000 onward so researchers can study political money alongside officeholding, legislation, votes, and place-based conditions. The previous machine-local FEC archive cannot support that goal: it has no rebuild path, full evidence ledger, or safe politician bridge.

## Capabilities

- **CAP-1**
  - **intent:** An operator can preview each bounded official FEC selection and see its exact files, availability, sizes, storage requirement, and approval state before downloading it.
  - **success:** An unknown/missing publisher size stops before transfer; an approved preview emits a versioned manifest and capacity result without writing campaign-finance facts.
- **CAP-2**
  - **intent:** An operator can run and repeat a small official 2024 candidate/committee/linkage/`pas2` pilot from a fresh clone.
  - **success:** The pilot retains official URLs, checksums, immutable artifact versions, and run evidence; a repeat reuses verified bytes and produces the same source-shaped stage result.
- **CAP-3**
  - **intent:** A researcher can query practical official FEC campaign-finance coverage for every available cycle from 2000 through 2024 through compact typed facts rather than a generic JSON staging table.
  - **success:** Every target family × cycle has a recorded resolution in the coverage matrix. Loaded cells have retained official evidence, a field checklist, reconciliation, idempotent reload evidence, and a resume path; a publisher-unavailable cell has official availability evidence; deferred or failed available cells remain visible and block a full-history completion claim.
- **CAP-4**
  - **intent:** A researcher can connect FEC candidate and committee facts to politicians only when a reviewed stable identifier path proves the connection.
  - **success:** A candidate-keyed fact links through an FEC candidate identifier and BioGuide-backed person only after the configured gate is enabled; name collisions, unresolved candidates, and committee-only records remain FEC-native and are reported.
- **CAP-5**
  - **intent:** A researcher can distinguish itemized contributions, committee/candidate transfers, operating expenditures, and reported totals before drawing conclusions from campaign-finance data.
  - **success:** Research views document their row grain, reporting period, amendment/version treatment, source family, and coverage limits, with drill-through to the retained official file.

## Constraints

- Acquire raw files only from original FEC endpoints into `DATA_ROOT`; never use a machine-specific legacy archive as a project input or rebuild proof.
- Retain source URL, checksum, immutable artifact version, manifest, and run evidence. Unknown size fails closed; raw evidence is never overwritten.
- Candidate/committee masters and linkage load before transactions. Facts use compact typed, cycle-partitioned grains; source-shaped stage records are retained only for parsing/replay, not as the research contract.
- Every selected family and cycle requires field disposition, publisher availability, capacity approval, reconciliation, idempotency, restart, and provenance evidence before it can be called complete.
- Person linking uses stable identifiers only and calls `identitygate.require_person_join`. Candidate, committee, donor, and filer display names are never join keys.
- Reuse external software only behind an adapter after license, maintenance, input/output, security, and provenance review. OpenDiscourse owns acquisition, evidence, canonical keys, and final schema.

## Non-goals

- Treating a successful raw download, a name match, or an itemized-contribution file as proof of all donations, all donors, or a political conclusion.
- Promoting FEC rows to politician-keyed facts before a reviewed identifier bridge enables the join.
- Building congressional investment-disclosure ingestion, securities analysis, or an opaque political/corruption score in this programme.

## Success signal

A fresh clone can reproduce an approved FEC batch from official evidence and researchers can safely compare clearly labeled money flows across the available 2000–2024 cycles. Every politician connection is identifier-backed or visibly unresolved, and every aggregate can be traced to the exact official source files and coverage rules behind it.

## Assumptions

- “Practical coverage” means the specified FEC bulk families wherever the FEC publishes an equivalent cycle product; a missing publisher product is a reported coverage limit, not a failed zero-value load.

## Open Questions

- Which source-native amendment/version rule is required for each FEC bulk family so that research marts can distinguish the latest report from superseded activity?
- After field inventory and benchmark, what is the smallest safe initial historical batch beyond the 2024 pilot?
