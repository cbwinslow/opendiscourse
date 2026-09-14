# Source sequencing

## v1 loadable spine

Identities, TIGER geography, legislation (Congress.gov, GovInfo, OpenStates
FDW), census/housing (existing contracts), sparse macro (FRED, Treasury,
bounded BLS).

## v1.1 (blocked on CAP-4 identity)

FEC campaign finance, politician investments/disclosures, elections, FBI/crime.

## Not a product domain

News, stocks/CFA, Epstein-as-schema, corruption scores.

## Already true on the cluster

- Database name `opendiscourse` (234 GiB, port 5434).
- OpenStates 38 GiB stays in database `openstates`; 11 OCD relations mapped
  via FDW. Do not merge the dump.
- `vector` extension 0.8.5 installed; `core.embedding` still portable `real[]`.
