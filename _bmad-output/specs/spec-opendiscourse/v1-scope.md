# Source sequencing

## v1 loadable spine

Identities, TIGER geography, legislation (Congress.gov, GovInfo, OpenStates
FDW), census/housing (existing contracts), sparse macro (FRED, Treasury,
bounded BLS).

## v1.1 (do not start in v1)

- **Politician joins** (FEC/disclosure/elections-as-member): blocked on CAP-4
  BioGuide identity. Never name-match.
- **FEC-native and crime-native staging:** not identity-blocked; still v1.1.
  Open only with Epic 7 after the v1 spine and Epic 8.

## Not a product domain

News, stocks/CFA, Epstein-as-schema, corruption scores.

## Already true on the cluster

- Database name `opendiscourse` (234 GiB, port 5434).
- OpenStates 38 GiB stays in database `openstates`; 11 OCD relations mapped
  via FDW. Do not merge the dump. Do not treat FDW as the researcher
  contract; promote into `core` (AD-8).
- `vector` extension 0.8.5 installed; `core.embedding` still portable `real[]`.
