---
title: 'Story 9.5 - BILLSTATUS Connector (download, inventory, ingest)'
type: 'feature'
created: '2026-09-19'
status: 'in-review'
baseline_commit: 'f0aa0df'
route: 'dispatch'
context:
  - '{project-root}/docs/PROJECT-STATE.md'
  - '{project-root}/docs/data-acquisition-plan.md'
  - '{project-root}/docs/adr/0003-load-strategy.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Bills, actions, sponsors, committees and subjects for Congresses 108-117 are not loaded (about 134K bills), and the loaders that exist read the operator's legacy lake by a fixed path, so nobody else could reproduce the database.

**Approach:** One Connector, `congress.govinfo_billstatus`, that downloads the GovInfo BILLSTATUS zips from the origin into `DATA_ROOT`, registers them as immutable artifacts, verifies them against GovInfo's directory manifest, and loads `core.bill` and its child tables. One command (`research-db sync-billstatus`) is the whole workflow and is safe to rerun.

## Boundaries & Constraints

**Always:** Bytes come from `govinfo.gov` (HTTP in `providers/govinfo.py`, paced, User-Agent, retry once on transport/429/5xx) and land in `DATA_ROOT` checksum-named through the existing `bulk.download`. A registry row is reused only if its retained file verifies, its recorded origin size and `Last-Modified` equal what a HEAD returns now, and its size matches. A registry row with no recorded origin state (anything written before this Connector) is re-verified by downloading, never trusted. A refreshed zip is a new artifact version; its rows replace the older version's for the same bills in one transaction. Unknown or unusable size, an unreadable zip, a member that is not the bill its file name and zip promise, or a capacity refusal fail before any write. A manifest that disagrees with the zip loads the bills, records `coverage: partial` on the artifact, and marks the run partial (exit code 2). Every load is recorded in `ingest.run` / `ingest.run_target` per Congress. Sponsors join to people by BioGuide id only. Set-based batches (default 500 bills per transaction), resume by member.

**Never:** No fixed path, no read of the legacy lake. No dispatcher branch in `cli.py` beyond one command, none in `plans.py` or `registry.sync`. No wipe or overwrite of retained bytes. No name matching. This story does not remove the old fixed-path loaders (`legload`, `legvalidate`, `legarchive`, `govbackfill`, `govplan`, `legreconcile`); that is the next story. No bill text, amendments, votes or member terms.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First sync | nothing registered | HEAD, capacity gate, download, register, compare manifest, load, mark `loaded` | any failure leaves the run `failed`; rerun resumes |
| Unchanged rerun | registered, origin size and date equal | no download, no load, 0 rows changed | N/A |
| Killed mid-load | some batches committed | rerun skips loaded members, ends equal to a clean load | interrupted batch rolled back |
| Origin refresh | size or `Last-Modified` changed | new artifact version, older version's child rows for those bills deleted, no duplicates | stale `.part` from before the change is discarded |
| Legacy registry row | registered without origin state | re-download; same bytes keep the version and gain origin state | N/A |
| Truncated download | bytes differ from HEAD size | fail; next run refetches | never ingested |
| Zip vs manifest | GovInfo lists a bill the zip lacks | bills load, artifact `coverage: partial`, run `partial` | reported in `incomplete_zips` |
| Malformed XML member | one member unparseable | skipped and listed; zip not marked `loaded`; run `partial` | N/A |
| XML contradicts its file name | number differs | member skipped and listed in `problems`; nothing written for it; run `partial` | one bad member never blocks the rest |
| Type not published | GovInfo answers 404 for a zip | listed in `not_published`; not an error | all requested zips absent: run `failed` |
| Unknown Congress | `--congress 500` | error naming the published range | run `failed` |
| Two syncs at once | a second `sync-billstatus` starts | refused at once (advisory lock) | no run row is created |
| Killed mid-zip | batches committed, then failure | `run_target` for the Congress is `partial` with the committed count | rerun writes the rest and records `succeeded` |

</frozen-after-approval>

## Code Map

- `src/opendiscourse_research/providers/govinfo.py` -- new: HEAD, root and type manifests, `member_identity`.
- `src/opendiscourse_research/ingestion/billstatus.py` -- new: `BillStatusConnector`, ten stages.
- `src/opendiscourse_research/repositories/billstatus.py` + `sql/query/legislation/supersede_bill_children.sql`, `superseded_artifact_ids.sql` -- refresh handling.
- `src/opendiscourse_research/repositories/legislation.py` -- `_query` cached; `save_billstatus_bill(person_cache=...)`.
- `src/opendiscourse_research/cli.py` -- `sync-billstatus`.
- Reused unchanged: `ingestion/bulk.download` (resumable, checksum, registry), `capacity.storage_preview`, `parse_billstatus_xml`, `IngestionRun.record_target`, `repositories/artifacts.get_current_artifact`. `research-db coverage` finds the zips through the same registry key.

## Tasks & Acceptance

**Execution:**
- [x] provider, Connector, repository, CLI command
- [x] `tests/test_govinfo_provider.py` (25), `tests/test_billstatus_unit.py`, `tests/test_billstatus_connector.py` (17 DB tests against a fake origin for synthetic Congress 998, including the ADR-0003 harness: run twice, wipe and reload, kill and resume at three points)
- [x] live: download all Congresses, load 108-119, then `research-db coverage` (result in Implementation Notes)
- [x] `docs/PROJECT-STATE.md`, `docs/data-acquisition-plan.md`, `epics.md`

**Acceptance Criteria:**
- Given an empty `DATA_ROOT`, when `research-db sync-billstatus` runs, then every zip is downloaded, registered with URL, size, checksum and `Last-Modified`, and every bill is loaded.
- Given an unchanged origin, when it reruns, then it downloads nothing and changes no row.
- Given `research-db coverage`, then bills loaded equal the official manifest count for every Congress and type that the zip covers.

## Implementation Notes

- The measured loader speed was 15 bills/s on the first real load (cosponsor-heavy 108th `hconres`). A profile showed 27% of the time re-reading SQL files from disk and a third of the round trips repeating sponsor lookups. `_query` is now cached and sponsor lookups are memoized per run: 2.1x faster, about 65 bills/s in the same profile.
- Actions, sponsorships, committees and subjects key on `source_artifact_id`, so loading a refreshed zip beside the old version would duplicate every row. Hence the supersede step. `core.document` rows key on the text-version URL and are not duplicated.
- Mutation-checked: disabling the supersede step and disabling change detection each fail `test_changed_origin_appends_a_version_and_replaces_the_old_rows`.

- Live result (2026-09-19): 96 zips, 572 MB, all matching GovInfo's manifests. `research-db coverage`: bills loaded equal official for Congresses 108-118 and actions equal the zips for all 12; 119th is 18,962 vs 18,956 official (6 "Reserved for the Speaker/Minority Leader" bills from a `congress.gov` source). 172,709 bills, 929,756 actions, 2,272,151 sponsorships (all resolved by BioGuide). A no-op rerun downloads and loads nothing.
- The live run's first pass reported `partial` for 13 files that spell identity `<billType>/<billNumber>`; fixed in `parse_billstatus_xml` and `legreconcile._bill_details`, tested, and the 13 loaded on a targeted rerun.
- CodeRabbit on PR #45 (5 comments): fixed the supersede query (strictly older versions only), added a run-level advisory lock (a second sync is refused), and made the ledger record every committed batch (a killed run shows its real work as `partial`); fixed the inconsistent archive sizes in the docs (one measured total: 574,316,859 bytes). Recorded, not changed: `core.bill_document` has no artifact provenance so a refresh cannot retract a text version (upstream only adds them); and `bill_type_and_number` stays beside `parse_billstatus_xml`, which already lives in `repositories/legislation.py`.
- Independent review (`/code-review high`): 11 findings, 8 fixed (shared paced client, unpublished zips non-fatal, identity mismatch skips instead of aborting, exit codes, de-duplicated bill types, own query loader, docs), 3 explained (capacity gate measures `DATA_ROOT` only; refresh reloads the whole zip, recorded as a known cost; `congresshealth` is legacy and goes with the old loaders).

## Verification

- `just check-fast` -- pass. `just check-db` -- pass (serial). `uv run research-db coverage`.
