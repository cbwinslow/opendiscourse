---
title: 'Story 9.5b - Lossless BILLSTATUS ingestion and typed promotion'
type: 'feature'
created: '2026-09-19'
status: 'in-review'
baseline_commit: '7b10ec9'
route: 'dispatch'
context:
  - '{project-root}/docs/PROJECT-STATE.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-9-5-billstatus-connector.md'
  - '{project-root}/docs/adr/0002-schema-invariants.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `parse_billstatus_xml` keeps a fraction of each BILLSTATUS file. A survey of all 172,703 files found 418 distinct element paths; the parser reads about 60 of them. CRS summaries, amendments, related bills, laws, CBO estimates, committee reports, alternate titles, action detail (committees, recorded votes, calendar, source system) and every text format but the first are dropped.

**Approach:** Store every bill's full record as jsonb, keyed by artifact and member, in the same transaction as the typed rows, so nothing the source says is lost even before it is modelled. A test proves the record captures every XML path (fast, on real fixtures) and a slow corpus test proves it on every member of every zip on the machine. Then promote summaries, laws, related bills and amendments to typed tables.

## Boundaries & Constraints

**Always:** Record and typed rows are written by the Connector's existing batched transaction and carry `source_artifact_id` + `source_member`. A refreshed zip is a new artifact version; the older versions' record and typed rows for the bills it rewrites are deleted in the same transaction (as for actions, sponsorships, committees, subjects). A member is "loaded" when it has a record row, so bills loaded before this story are reloaded once (idempotent upserts) to gain theirs. Leaf text is stripped of layout whitespace and otherwise verbatim. An element with attributes, or with text beside child elements, is kept (`@name`, `#text`); non-whitespace tail text raises so a member is reported malformed instead of silently losing it. Sponsors of amendments join to people by BioGuide id only.

**Never:** No new Connector, dispatcher branch or CLI command. No fixed path (the corpus test reads `DATA_ROOT`, skips when absent). No name matching. No wipe of retained bytes. No new ingest of bill text, votes, CBO or committee-report typed tables (they live in the record; promotion is a later story). No change to what `core.bill`, `bill_action`, `bill_sponsorship`, `bill_committee`, `bill_subject` receive.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Any member | valid BILLSTATUS XML | one `core.bill_source_record` row whose record has every element path and leaf value of the XML | N/A |
| Repeated / singleton lists | `item`, `summary`, `link`, `amendment`, `recordedVote`, `committeeReport` | always a JSON array, even with one child | any other repeated tag also becomes an array |
| Namespaced tag | `dc:*` in `dublinCore` | key `dc:<name>` | unknown namespace keeps Clark notation |
| Bill loaded before this story | bill and children exist, no record | reloaded once; children upsert without duplicates; record added | N/A |
| Origin refresh | new artifact version | older version's record and typed rows for those bills deleted, new ones written, no duplicates | failure rolls the whole batch back |
| Alternate spelling (13 files) | `summaries/billSummaries/item`, `billType`/`billNumber` | summaries still promoted | N/A |
| Duplicate scalar children | 173 amendments in 115hr3354 repeat `number`, `congress`, `type` | typed row takes the first; record keeps all as an array | N/A |
| Unchanged rerun | every member has a record | nothing downloaded, nothing loaded | N/A |

</frozen-after-approval>

## Code Map

- `src/opendiscourse_research/ingestion/billstatus_record.py` -- new: `xml_to_record`, path and leaf comparison helpers.
- `src/opendiscourse_research/repositories/legislation.py` -- `parse_billstatus_xml` adds `record`, `summaries`, `laws`, `related_bills`, `amendments`; `save_billstatus_bill` writes them.
- `src/opendiscourse_research/repositories/billstatus.py`, `sql/query/legislation/*` -- supersede and resume queries, new upserts.
- `src/opendiscourse_research/models/core.py`, `migrations/versions/` -- five new `core` tables.
- `src/opendiscourse_research/ingestion/billstatus.py` -- resume by record.
- `tests/test_billstatus_record.py`, `tests/test_billstatus_record_corpus.py`, `tests/test_billstatus_lossless_db.py`, `tests/fixtures/billstatus/` -- real, small files chosen by greedy set-cover over all 418 paths.
