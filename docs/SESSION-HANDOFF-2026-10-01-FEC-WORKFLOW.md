# Session handoff: reproducible FEC workflow (2026-10-01)

## Plain goal

Make Federal Election Commission (FEC) campaign-finance data usable alongside
the existing congressional data **without guessing identities**, and make the
whole workflow reproducible for a person starting from a fresh GitHub clone.

The operator chose FEC before congressional investment disclosures. Do not
start investment-disclosure ingestion in this slice.

## Start here

Read, in order:

1. `AGENTS.md`
2. `docs/PROJECT-STATE.md`
3. `_bmad-output/specs/spec-fec-reproducible-ingest/SPEC.md`
4. `_bmad-output/specs/spec-fec-reproducible-ingest/reuse.md`
5. `inventory/sources.yaml` entries `fec.campaign_finance` and
   `disclosures.financial`
6. `inventory/contracts/fecbulk.yaml`

Use the project skills `opendiscourse-connector`,
`opendiscourse-provenance`, and `opendiscourse-testing`. This is a medium
source change: follow the repository rule to plan/spec it before build work.

## What is already true

- Legislative data is live: bills, votes, members, committee membership, bill
  text, and CBO estimates are loaded as described by the legislative north star.
- `core.person` is the central politician record. It has BioGuide identity and
  carries known external identifiers, including FEC candidate IDs where the
  upstream legislator record supplies them.
- FEC data is **not** a reproducible loaded source. Legacy FEC files and a
  preliminary `stage.fec_row` area exist, but they came from a machine-specific
  path. Do not use them as the project input or claim them as a rebuild.
- `fec.campaign_finance.person_join` is blocked. Do not link people by name.
  A future person link must use the existing FEC identifier to BioGuide path
  and an approved candidate/committee linkage contract.
- `disclosures.financial.person_join` is also blocked. The disclosure portals
  do not yet supply an identifier bridge we can safely use; this is why
  congressional investments are deferred.

## FEC goal and sequence

1. Build a Connector that discovers official FEC files and makes a manifest
   before it transfers any bytes.
2. Start with a bounded, completed **2023–2024** cycle pilot: candidate master,
   committee master, candidate-to-committee linkage, and the small `pas2`
   committee-to-candidate transaction file. This proves source files,
   candidate/committee relationships, evidence retention, and resumable stage
   loading without beginning with the multi-gigabyte individual-contribution
   files.
3. Capacity-gate the pilot. Unknown source sizes must stop before download.
4. Retain every official file under the operator's `DATA_ROOT` with source URL,
   checksum, artifact version, and `ingest.run` evidence. Never overwrite raw
   evidence.
5. Stage FEC-native data first. Verify the candidate/committee identifier
   bridge and report unresolved records. Do not promote person-keyed facts or
   enable the person join until its contract is reviewed and approved.
6. After the pilot passes repeatability, approve the compact typed FEC model,
   field inventory, amendment/version rule, and representative-cycle benchmark.
   Then load candidate/committee masters and linkage before transactions.
7. Expand in approved, capacity-gated batches to every available cycle from
   **2000–2024** for itemized individual contributions, `pas2`, other
   transactions, operating expenditures, and reported summary/total products.
   Each family/cycle must reconcile, prove restart safety, and report coverage;
   a missing publisher product is a visible limitation, not a zero.
8. Open the FEC-to-politician bridge only after a separately reviewed stable-ID
   contract and exception report. Publish researcher marts only after the
   underlying coverage and identity dependencies are complete.

The FEC's official bulk catalog provides candidate, committee, candidate-
committee linkage, individual contribution, and committee-to-candidate files
for the 2023–2024 cycle. The FEC page describes the linkage file as one row per
candidate-to-committee relationship and describes `pas2` as committee/PAC/
party/candidate contributions or independent expenditures to candidates.

## Reuse research

The full review is in `reuse.md` beside the FEC spec.

- FEC's own bulk files and OpenFEC metadata are the source of truth.
- `fecfile` is a Python raw-`.fec` filing parser. It may help with a later
  raw-filing path, but it does not replace the bulk-file Connector.
- `hardmoney` claims Python/Rust support for FEC parsing and bulk loading. It
  may be tested behind an adapter, but its schema and loader must never write
  OpenDiscourse core/fact tables directly.
- `fec-pipeline` is useful reference code for bulk downloading and FEC linkage
  files, but not a project to embed: it is a much broader SQLite application.
- `congressional-disclosures` is the leading later candidate for House/Senate
  investment disclosures. It retrieves official documents and retains source
  URLs/hashes, but its hosted snapshot is not project evidence and the
  identifier bridge remains unresolved. Do not work on it in the FEC slice.

Always search for maintained upstream projects and libraries before writing a
new source implementation. Reuse only behind an adapter after checking its
license, maintenance, input/output behavior, security, and provenance fit.
OpenDiscourse remains responsible for official acquisition, immutable
evidence, stable keys, and canonical tables.

## Safety boundaries

- Do not download or stage FEC files until the pilot manifest and capacity
  preview are available and the operator explicitly approves the transfer.
- Do not read `/mnt/...` or another machine-specific archive as a default
  source. The project must work from original FEC endpoints for a new clone.
- Do not join any FEC candidate, committee, donor, or disclosure filer by
  display name.
- Do not promote `stage.fec_row` to final campaign-finance facts before a
  source-specific schema and identity contract are approved.
- Do not start FEC, disclosure, elections, or crime work through a new
  `cli.py`, `plans.py`, or `registry.sync` branch. Use a Connector.
- Do not modify or restart the active ACS/AHS service.

## Separate dirty worktree items

The workspace is intentionally dirty and shared with other sessions. Preserve
all changes that are not part of the FEC work.

- ACS files: `src/opendiscourse_research/ingestion/acs_archive.py` and
  `tests/test_acs_archive.py` belong to the separate active ACS staging work.
  Do not edit, commit, revert, or restart it here.
- Congress 120 readiness files are uncommitted and incomplete after review.
  They are unrelated to FEC and must not be included in an FEC commit. Do not
  resume, commit, or revert them without a new operator decision.
- The FEC spec folder is new, uncommitted planning work. It is not an
  authorization to transfer FEC bytes.

## Current status

- Done: FEC source, reuse, coverage/grain, and completion specifications.
  The 2000–2024 target, source-family distinctions, evidence, capacity,
  identity, reconciliation, and research-mart gates are now explicit.
- Candidate implementation exists for the bounded Connector, official
  URL/size adapter, disabled contract, and offline malformed-size/approval/
  parser tests. It still requires independent review before it is described as
  a finished pilot.
- Next: complete the read-only field/coverage inventory and compact-model
  design, then independently review the pilot. Only afterward may a fresh
  official manifest be generated for transfer approval.
- Blocked by design: all transfer remains blocked by a fresh manifest,
  capacity preview, and operator approval. Person bridging remains blocked by
  its separate reviewed stable-ID contract; no name-based link is permitted.
