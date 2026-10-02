# Sprint Change Proposal — FEC and OpenStates research spine

## Issue summary

The approved FEC pilot proves a small official download path but does not meet
the operator's actual goal: reusable U.S. political research from 2000 onward,
including meaningful campaign-finance analysis and state/local political
coverage. Existing guidance also limits hot FEC facts to six years and leaves
the full OpenStates snapshot underused. The operator has clarified that
OpenStates is a major credible upstream source to leverage, not recreate.

Evidence: the OpenStates snapshot is already restored separately (84 tables,
about 98.8M rows); existing FEC JSON staging is about 102M rows/74GB and is
too wide for historical expansion; recent `indiv` files are multi-GB compressed.

## Recommended approach

Adopt a staged direct adjustment, not rollback. Keep the four-file 2024 FEC
pilot as the reproducibility gate, then add a reviewed full-history programme.
Keep the full OpenStates snapshot as a read-only source database and promote
research grains into owned tables; never copy its Django schema as canonical.

## Architecture and data model

1. Retain every official FEC cycle ZIP (2000–2024) immutably with run, URL,
checksum, and version evidence.
2. Use compact typed, cycle-partitioned tables: candidate master `(cand_id,
cycle)`, committee master `(cmte_id, cycle)`, candidate-committee linkage
`(cand_id, cmte_id, fec_election_year)`, individual contribution and other
transaction facts keyed by `(sub_id, cycle, family)`.
3. Preserve raw stage only for parsing/replay; do not make JSONB the analysis
store. Use candidate/committee summaries to represent unitemized totals and
avoid claiming `indiv` is all donations.
4. Promote OpenStates people, jurisdictions, organizations, posts,
memberships, sessions, bills, actions, sponsorships, vote events and person
votes as typed, provenance-linked rows from the snapshot.
5. Build a cross-source identity layer from stable IDs only: BioGuide, OCD
person ID, FEC candidate ID, and other reviewed namespaces. No display-name
matching. Unresolved people stay useful in their source domain.
6. Build marts for politician-by-cycle finance, committee/candidate flow,
outside spending, and state/federal office history; every metric links back to
source evidence and documents coverage limits.

## Required backlog changes

- Replace Epic 7's TBD money work with: FEC reusable Connector; FEC typed
schema/migration and partitions; 2000–2024 masters/linkage; phased historical
transaction loading; reviewed politician bridge; finance marts.
- Expand OpenStates promotion from the existing bounded federal-vote path to
a source-wide, dependency-ordered promotion programme.
- Amend the FEC retention rule in SPEC/resolved questions: all cycles remain
queryable in partitioned facts; derived Parquet is an export, not the only
older-history access path.
- Add a source field checklist and count/reconciliation contract for each FEC
family and OpenStates promoted grain.

## Sequencing and gates

1. Finish independent review of the existing FEC pilot; no transfer yet.
2. Create an ADR and Alembic design for compact FEC facts and OpenStates
promotion keys; benchmark a representative cycle before loading history.
3. Run official manifests and capacity previews; operator approves each
bounded transfer batch.
4. Load masters/linkage first, then transactions cycle-by-cycle with resume,
reconciliation, and coverage reports.
5. Open the politician bridge only after its stable-ID contract and tests are
approved; then publish marts and API views.

## Impact and handoff

This is a major replan: it changes Epic 7, the FEC specification, the
architecture's retention decision, inventory contracts, and future migrations.
It does not change the PRD vision, does not need UI work, and does not justify
copying OpenStates' internal schema. Product/architecture approval is required
before developer implementation; developer work follows the approved ADR/spec.

## Approval decision

Approve this proposal to replace the pilot-only FEC path with the phased
2000–2024 FEC plus OpenStates promotion programme. No bulk transfer or schema
change is authorized by this document alone.
