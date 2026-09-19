# Writers and delivery order

## Writers to change (code at 2026-09-19)

| Entity | Writer | Location | Change |
|---|---|---|---|
| person | legislators promote | `repositories/people.py`, `sql/query/people/insert_new_legislator_people.sql` | already locked; add assertion; keep BioGuide lookup, add any-identifier lookup |
| person | OpenStates federal people | `repositories/legislation.py` `sync_openstates_federal_people`, `sql/query/legislation/upsert_person_by_ocd.sql` | look up by any identifier (uses the BioGuide id in `openstates_person_identifiers.sql`), take the person lock, assertion |
| person | Congress.gov member | `repositories/legislation.py` `upsert_congress_person` (SQLAlchemy and psycopg paths), `upsert_person_by_bioguide.sql`; caller `ingestion/congress.py:96` | take the person lock, any-identifier lookup, assertion |
| person | conflict report | `promote_legislators` `legislator_identifier_conflicts` | extend to the other writers |
| geography | TIGER (name, overwrite) | `ingestion/tiger_load.py:141` | assertion short and full |
| geography | PEP (first non-null) | `ingestion/pep_load.py:117` | assertion full (`CTYNAME`) |
| geography | ACS API (overwrite) | `ingestion/census.py:50-62` | assertion full; stop writing `name` |
| geography | ACS bulk, DHC, CBP (create row, no name) | `ingestion/acs_load.py:170`, `dhc_load.py:131`, `cbp_load.py:154` | shared FIPS derivation; no name write |

## Story order

1. **Identity fix, lock and duplicate merge** (CAP-1, CAP-2, CAP-3). Independent of names; ships first. Includes the identity order test and applying the Stutzman exception on a scratch copy, then live.
2. **Assertion tables, precedence file and sync, resolver, guard** (CAP-4 schema, CAP-5, CAP-6). Includes concurrent-resolver, idempotency, guard and fail-closed tests.
3. **Geography loaders** (CAP-4): the six writers above, including ACS.
4. **Person loaders** (CAP-4): the three writers, on top of story 1.
5. **Backfill** (CAP-7): scratch copy first, then live.
6. **Rebuild kit verify** (CAP-8): hook into `_bmad-output/specs/spec-rebuild-kit/`.

Tests ship with each story (failure, idempotency, resume, provenance where they apply).
