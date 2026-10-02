---
id: SPEC-political-research-marts
companions:
  - mart-catalog.md
  - ../spec-openstates-political-core/SPEC.md
  - ../spec-fec-reproducible-ingest/SPEC.md
sources:
  - ../../../docs/mart.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# Provenance-backed political research marts

## Why

The normalized warehouse is necessary for trustworthy ingestion, but researchers need clear, stable analytical tables rather than repeatedly rebuilding complex joins. These marts make political research practical while preserving the important distinctions between measured facts, missing coverage, unresolved identities, and derived measures.

## Capabilities

- **CAP-1**
  - **intent:** A researcher can use named political marts for people, office terms, member votes, bills, candidate-cycle finance, and district-year context.
  - **success:** Every published mart declares its row grain, stable key, time basis, source dependencies, coverage status, and link back to underlying source evidence.
- **CAP-2**
  - **intent:** A researcher can tell a true zero apart from data that was not available, not loaded, not comparable, or not safely linked to a person.
  - **success:** Each mart has documented availability/coverage fields and tests covering at least one unavailable, unresolved, and measured-zero case where the source supports those states.
- **CAP-3**
  - **intent:** A researcher can join compatible political, finance, legislative, and geographic results without silently changing the meaning of a row.
  - **success:** Semantic tests reject duplicate keys and incompatible time/geography joins; a historical membership or finance fact never receives a current-boundary district value without an approved vintage relationship.
- **CAP-4**
  - **intent:** A researcher can reproduce a mart-derived conclusion from the underlying facts and evidence.
  - **success:** Documentation names source datasets, transformations, identity gates, aggregation rules, and known limits; every output metric can be traced to a bounded core/fact query.

## Constraints

- dbt owns `mart`; canonical identity, provenance, and factual tables remain in `core`/`fact`.
- One mart has one declared grain. A convenience column may not conceal a one-to-many expansion, mismatched reporting period, or duplicate source record.
- Do not create person joins from display names or expose a FEC-to-politician metric before the identifier bridge is enabled.
- Preserve historical time and geographic vintage. Do not compare or aggregate district values across redistricting without a reviewed relationship/crosswalk rule.
- Derived measures must state their formula and source coverage. Opaque political effectiveness, bias, integrity, or corruption scores are out of scope.

## Non-goals

- Exposing `stage`, raw artifact paths, or the OpenStates FDW as the normal researcher interface.
- Claiming nationwide, all-office, or all-money coverage where a mart's dependent sources have not met their completion contract.
- Replacing the source-specific FEC and OpenStates completion gates with a dashboard or a flattened export.

## Success signal

A political researcher can select a documented mart, understand one row without opening implementation code, and trace any figure to its source evidence and stated limits. An incomplete source or ambiguous person relation remains visible instead of becoming a misleading blank or zero.

## Assumptions

- A mart may be specified before it is published, but its catalog status remains `planned` until all listed dependencies and tests are complete.
