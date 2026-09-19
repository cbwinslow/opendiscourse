# Assertion model

## Tables

- `core.person_name_source`, `core.geography_name_source`. One row per (entity, `name_kind`, `dataset_id`, `source_vintage`); unique index `NULLS NOT DISTINCT` on that natural key so reruns are idempotent and evidence moves in place (pattern: `sql/query/.../upsert_term_memberships.sql`).
- Columns: entity id; `name_kind` (person: `official`, `common`; geography: `short`, `full`); the value(s) exactly as given (a person's full/given/family triple travels together from one assertion); `dataset_id` FK `catalog.dataset`; `source_vintage` (release year or period); `artifact_id` nullable, `payload` nullable, `run_id` (ADR-0002 rule 3: artifact OR payload, plus run; OpenStates and Congress.gov members have no artifact).
- ZCTA name assertions are skipped (the name equals the geoid).
- Resolved columns: `core.person.full_name/given_name/family_name` and `core.geography.name`, each with `name_source_id` FK to the winning assertion. `state_fips`/`county_fips` come from one shared derivation from the geoid, not five write rules.
- Merge audit (CAP-3): a table preserving deleted colliding `fact.member_vote` rows, keyed by survivor, duplicate, roll call.
- Conflict record (CAP-2): written to the existing identifier-conflict report path; extend it rather than add a parallel one.

## Precedence

`inventory/precedence.yaml` lists, per entity, per attribute, per `geography_type`, the ordered sources and the field each maps to; synced by a keyed sync into `catalog.attribute_precedence`. Resolution: highest-ranked source that has an assertion, then `source_vintage` DESC, then natural key `COLLATE "C"`.

| Entity / attribute | Order (best first) | Field notes |
|---|---|---|
| person `official` name | `congress.legislators` > `congress.legislation` (Congress.gov members) > `openstates.legislation` | display column's `name_kind` choice recorded in the file; default reproduces live names |
| person `common` name | `openstates.legislation` > others | only if operator picks common (open question) |
| geography `short` name | `census.tiger` | `NAME`; PEP has no `NAME` (`CTYNAME` is the county, `STNAME` the state), so PEP supplies `full`, not `short` |
| geography `full` name | `census.tiger` `NAMELSAD` (county, CBSA; loader must start reading it) > PEP `CTYNAME` > ACS `NAME` | ACS API writer is `ingestion/census.py:50-62`, e.g. "Autauga County, Alabama" |

Mapping is per `geography_type`, not one rule. A dataset with assertions and no precedence row fails closed.

## Resolver

`research-db resolve [--dry-run] [--entity person|geography]`. Pure function of committed assertions; updates only rows whose result changed and reports them from `RETURNING`; runs after each loader's commit; one final global dry-run in kit verify must show zero changes.

## Backfill and rollback

Pre-image CSV of the rows that will change; `resolve --dry-run`; assert expected diff (246 people = 245 OpenStates-first + 1 Congress.gov `G000608`; by column 217 `full_name`, 103 `given_name`, 7 `family_name`; no geography name change; live counties 3,244 and states 56 already equal TIGER short `NAME`); apply; record in the run ledger and `docs/PROJECT-STATE.md`. Rollback restores values by flipping precedence, not schema.
