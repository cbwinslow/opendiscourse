---
id: SPEC-housing-microdata-archive
companions:
  - product-and-field-policy.md
  - ../spec-longitudinal-source-coverage/SPEC.md
  - ../../spec-opendiscourse/SPEC.md
sources:
  - ../../../inventory/contracts/acscomprehensive.yaml
  - ../../../docs/PROJECT-STATE.md
---

> **Canonical contract.** This SPEC authorizes a reusable, provenance-first implementation plan for full public housing-microdata retention. It requires capacity approval and a Connector before any bulk transfer.

# Full official housing microdata archive

## Why

OpenDiscourse needs nationwide, long-running evidence to evaluate how policy decisions relate to housing, people, and places. The warehouse will retain complete public ACS PUMS and American Housing Survey files where the publisher makes them available, while using a carefully governed analytic field layer to avoid needlessly duplicating the same information in canonical tables.

## Capabilities

- **CAP-1**
  - **intent:** The operator can download and retain every official ACS PUMS public file released from 2005 onward, for both 1-year and 5-year products, without replacing one product with the other.
  - **success:** The artifact manifest contains every current official U.S. and Puerto Rico housing/person CSV package, data dictionary, and release note for standard ACS 1-year releases in 2005-2019 and 2021-2024 and 5-year releases ending 2009-2024; the 2020 1-year absence is explicit.

- **CAP-2**
  - **intent:** The operator can download and retain the complete public AHS archive from 2000 onward, including every published national and metropolitan public-use component.
  - **success:** The manifest names every official AHS release available from 2000 onward, chooses the current version of each national/metropolitan CSV representation, preserves its codebook and release notes, and records any publisher year gap rather than inventing a release.

- **CAP-3**
  - **intent:** A researcher can use a broad, policy-relevant analytic layer over retained housing microdata and later add a documented field without re-downloading evidence.
  - **success:** Each source variable has an official definition, product/release applicability, value domain, and field-policy status; the initial analytic layer covers demographics, income, education, family/household structure, housing costs/value/quality, and employment while raw source records remain available for future promotion.

- **CAP-4**
  - **intent:** The operator can repeat a full source refresh or resume a stopped one without duplicate canonical records or loss of evidence.
  - **success:** The Connector discovers files and versions from official indexes, capacity-gates the exact selected manifest, stores immutable bytes/checksums, stages source-shaped rows, validates product/geography/vintage rules, publishes idempotently, and checkpoints each artifact.

## Constraints

- PUMS, ACS tabulated estimates, and AHS are separate products. Preserve their product, collection period, survey component, geography vintage, and variable definition; never describe a PUMS sample as identified households or county-level microdata.
- Retain complete raw current-version public files and dictionaries. The canonical analytic layer is a documented projection, not a destructive filter; adding a field later must reuse retained evidence.
- ACS 1-year supports annual change only for eligible larger geographies. ACS 5-year supplies nationwide small-area coverage. Both are required; neither can be recreated as the other by averaging or summing.
- Use original Census endpoints, `DATA_ROOT`, immutable artifact records, run lineage, capacity estimates, resume checkpoints, and a Connector. No source-specific CLI dispatcher branch or machine-local cache is permitted.
- Select exactly one current representation for each AHS component and release. Do not load both relational and flat copies as independent observations; retain superseded files only when needed as publisher evidence.
- Crime is a separate official data domain. Do not invent a crime field in ACS or AHS; its future source needs its own contract and identity rules.

## Non-goals

- This does not ingest private or restricted microdata, infer household identity, join people to politicians, or create a false ACS release for 2000-2004 or 2020 1-year.
- This does not discard broad source evidence because a field is not in the initial analytic projection.
- This does not interrupt the in-flight ACS 2021-2024 5-year detailed-table load.

## Success signal

The warehouse has a repeatable official-source archive and field catalog for ACS PUMS and AHS, with nationwide historical records and explicit geography/product limits. Researchers can analyze policy-relevant housing and household conditions while every result resolves to the original publisher artifact, and later field coverage can expand without reacquisition.

## Assumptions

- The preliminary official-index measure is about 64.10 GiB compressed for ACS PUMS and at most 3.68 GiB for all candidate AHS CSV PUF packages; the exact selected manifest and expanded storage are capacity-gated before transfer.

## Open Questions

- Should the first canonical microdata query surface be source-shaped, a typed shared household/person model, or both through a source-shaped stage plus reviewed marts?
- Do current-version AHS relational CSV packages plus codebooks satisfy “whole AHS,” or should the retained archive also include superseded publisher versions and flat copies as non-canonical evidence?
