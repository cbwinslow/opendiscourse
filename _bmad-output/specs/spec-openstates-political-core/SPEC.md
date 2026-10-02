---
id: SPEC-openstates-political-core
companions:
  - source-mapping.md
sources:
  - ../../planning-artifacts/sprint-change-proposal-2026-10-02.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate.

# OpenStates political-core promotion

## Why

OpenDiscourse needs a durable U.S. political research foundation, not a second, competing OpenStates database. The opportunity is to promote the useful records in the full OpenStates snapshot into owned, provenance-backed political tables that can be safely combined with Congress, FEC, and place-based evidence from 2000 onward.

## Capabilities

- **CAP-1**
  - **intent:** A researcher can use one stable political model for jurisdictions, sessions, organizations, offices, people, memberships, bills, actions, sponsors, documents, vote events, and individual votes regardless of whether their source was OpenStates or a federal provider.
  - **success:** The approved mapping proves each promoted record has an owned key, its source key, and evidence back to the retained source artifact or payload; representative state, local, executive, and federal records are queryable without relying on OpenStates physical table names.
- **CAP-2**
  - **intent:** An operator can determine exactly how every discovered OpenStates field is handled before bulk promotion.
  - **success:** A generated field inventory classifies every source column and nested public field as typed/searchable, retained source detail, or explicitly excluded with a reason; an unmapped new field fails the review gate.
- **CAP-3**
  - **intent:** An operator can repeatedly promote an approved snapshot without duplicate rows, guessed identities, hidden loss of source detail, or writes to the OpenStates source database.
  - **success:** A bounded real-data run records source and destination counts, unresolved references, source fingerprint, restart state, and evidence links; a rerun is idempotent and preserves the original evidence bytes.
- **CAP-4**
  - **intent:** A researcher can safely connect state/local officials to federal and campaign-finance evidence only where an auditable identifier bridge exists.
  - **success:** Tests show a verified identifier creates the intended link, while a same-name record, missing identifier, and disabled FEC bridge all remain unlinked and appear in an unresolved report.

## Constraints

- `openstates_source` is read-only source evidence. OpenDiscourse must not write to it or make upstream Django table names, indexes, or migrations its researcher-facing contract.
- Preserve OpenStates/OCD identifiers and the full source record detail alongside compact typed fields; never silently discard an unmapped field.
- Use the project Connector, artifact/run ledger, capacity gate, and source-version fingerprint. Source drift stops promotion until the inventory and mapping are reviewed.
- Use stable identifiers only for cross-provider people joins: BioGuide for federal people and the configured `person_join` gate for FEC. Display names, parties, districts, and offices are never identity keys.
- Model historical terms and boundaries with dates/vintages. Do not attach historical membership or election facts to an assumed current district boundary.

## Non-goals

- Copying OpenStates' Django schema, migration history, or provider database into the OpenDiscourse system of record.
- Treating the current snapshot as proof that every jurisdiction or historical period is complete.
- Enabling FEC person promotion, adding a political score, or acquiring a new OpenStates feed before the field/coverage inventory and separate approval.

## Success signal

An independent reviewer can start at an OpenDiscourse political fact and trace it to retained OpenStates evidence, see the source and mapping version used, and distinguish an identifier-backed cross-source connection from an unresolved record. A re-run of an approved snapshot reports the same reconciliation result without changing the source evidence.

## Assumptions

- The current read-only snapshot is the first source baseline. Its actual jurisdiction/entity/time coverage will be measured rather than inferred from its table names.

## Open Questions

- After the inventory, do documented OpenStates API/export entities absent from the dump require a separately approved acquisition path?
