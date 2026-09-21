# Global data spec

The data specification for OpenDiscourse. `inventory/` is the data SDD; this file is its entry point and holds the
rules every source follows. Software behaviour is specified in `_bmad-output/specs/spec-opendiscourse/SPEC.md`.

## What we are building

A database of U.S. public-policy data. For each source: download the original files from the publisher into the
user's `DATA_ROOT`, register them (artifact registry), load everything they contain into the warehouse, and keep the
record of how, so anyone can repeat it on their own machine. Then link the data together by stable identifiers.

## Rules for every source

1. **Take everything the source offers.** Every field, every record, every period, within reason. "Within reason" is
   decided in writing: a field or file we do not store is listed in the source's field checklist as `not_stored`
   with a reason. Silence is not allowed.
2. **Store the whole record first.** Keep each source record whole (raw file as an immutable artifact, and the
   full record as JSON in the warehouse where the file is many small records), then add typed tables for the fields
   people query. New typed tables come from the stored record, without downloading again. Model: BILLSTATUS,
   `core.bill_source_record` plus typed sections (Story 9.5b).
3. **Use the existing tool when there is one.** Search for a maintained project first (`reuse.md`); wrap it,
   own the evidence and the keys.
4. **Provenance.** Every row traces to an artifact (or payload) and a run. Retained files are never overwritten.
5. **Identity.** People join on BioGuide (or another identifier the source states), never on names. Sources that
   describe the same entity's name or attribute record assertions and are resolved by `inventory/precedence.yaml`
   (ADR-0005).
6. **Complete means measured.** Loaded counts are compared with the publisher's own counts
   (`research-db coverage`); a source is not "done" until that comparison is recorded.
7. **SQL lives in `sql/query/`**, not in Python strings.

## Field checklists

One file per dataset in `inventory/fields/<dataset_id>.yaml`. It says what the source offers and what we do with each
part. Format (checked by `tests/test_field_checklists.py`):

```yaml
dataset: <id from sources.yaml>
audited_on: 2026-09-20
origin: <where the files come from>
capture:
  whole_record: <table that holds the full record, or null>
  notes: <how the whole record is kept>
fields:            # group fields when there are hundreds; name every group
  - name: <field or group>
    status: typed | whole_record_only | not_stored
    where: <table.column or null>
    reason: <required unless typed>
```

Statuses: `typed` (own column), `whole_record_only` (kept in the stored record, not yet a column; the reason says
what would type it), `not_stored` (not kept; a reason is required, and only for content we decided is out of scope).

## Audit state (2026-09-20)

| Dataset | Checklist | State |
|---|---|---|
| `congress.govinfo_billstatus` | `fields/congress.govinfo_billstatus.yaml` | audited |
| `congress.govinfo_bills` | `fields/congress.govinfo_bills.yaml` | audited (Story 11.3); live run pending |
| `congress.house_votes` (Clerk XML, House) | `fields/congress.house_votes.yaml` | audited (Story 11.1); live run pending |
| `congress.senate_votes` (senate.gov XML) | `fields/congress.senate_votes.yaml` | audited (Story 11.2); live run pending |
| `congress.legislators` | none yet | **needs audit** |
| `congress.legislation` (Congress.gov members) | none yet | **needs audit** |
| `openstates.legislation` | none yet | **needs audit** |
| `census.*` (ACS, CBP, PEP, DHC, TIGER) | none yet | **needs audit** |
| FEC bulk | none yet | **needs audit** |
| FRED, Treasury | none yet | **needs audit** |

Each audit starts from the publisher's own field documentation and the raw file, compares it with what is stored,
and fixes or explains every gap. Unaudited sources are assumed incomplete.

## Where the rest lives

- Source catalog: `inventory/sources.yaml`; load plans: `inventory/plans.yaml`; contracts: `inventory/contracts/`;
  progress register: `inventory/progress.yaml`; name precedence: `inventory/precedence.yaml`.
- What exists to acquire and in what order: `docs/data-source-map.md`, `_bmad-output/specs/spec-opendiscourse/v1-scope.md`.
- The workflow every source follows: `docs/data-acquisition-plan.md`. Decisions: `docs/adr/`. Current status: `docs/PROJECT-STATE.md`.
