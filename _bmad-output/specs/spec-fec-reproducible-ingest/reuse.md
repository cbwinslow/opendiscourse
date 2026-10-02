# Reuse evaluation: FEC and congressional disclosures

This document records external projects assessed before writing source code. An
external project's parsed output is never substitute evidence: OpenDiscourse
still downloads from the original government endpoint and records its own URL,
checksum, artifact version, and run.

## FEC candidates

| Project | What it provides | Decision for the FEC pilot |
|---|---|---|
| [FEC bulk data](https://www.fec.gov/data/browse-data/?tab=bulk-data) and [OpenFEC](https://api.open.fec.gov/developers/) | Official bulk files and official API metadata. | Required source of truth for all acquisition and manifest checks. |
| [fecfile](https://github.com/esonderegger/fecfile) | Python parser for raw `.fec` electronic filing files, including streaming iteration. | Evaluate later if the workflow needs raw filing parsing. It does not replace the current pipe-delimited bulk-file pilot. |
| [hardmoney](https://github.com/cgorski/hardmoney) | Rust/Python package claiming FEC filing parsing, validation, and bulk loading. | Candidate for a bounded adapter smoke test only. Its Postgres schema and loader are not adopted; it must pass maintenance, license, input/output, and provenance review first. |
| [fec-pipeline](https://github.com/Brettchr301/fec-pipeline) | A broad Python/SQLite pipeline with FEC bulk download and candidate-committee-link examples. | Reference its public downloader and field-handling ideas; do not wrap its 37-phase, multi-source application or copy its SQLite schema. |

## Congressional investment-disclosure candidate — deferred

| Project | What it provides | Decision |
|---|---|---|
| [congressional-disclosures](https://github.com/austin-starks/congressional-disclosures) | An open-source, resumable House/Senate disclosure pipeline that retains source URLs, hashes, extraction status, amendments, and transaction ranges. | Strong leading candidate for a later disclosure-specific evaluation. Do not ingest its hosted snapshot as evidence; assess its license and adapter boundaries, then use its official-source sync path only if it satisfies OpenDiscourse provenance and identifier rules. |

## Adoption test

Before adding a dependency or vendor clone, the FEC implementation must show that
the candidate can parse one retained official fixture without network access;
preserves stable source keys and errors; is license-compatible; and can be called
without allowing it to write directly to OpenDiscourse `core` or `fact` tables.
