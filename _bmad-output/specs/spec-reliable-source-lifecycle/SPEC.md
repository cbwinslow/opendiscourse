---
id: SPEC-reliable-source-lifecycle
companions:
  - source-contract-and-status.md
sources: []
---

# Reliable source lifecycle

## Why

The ACS archive transfer demonstrated that a temporary failure at one official
download address can stop a large, otherwise valid acquisition. Operators also
need one clear answer to what a source intends to collect, what evidence is
retained, and what has been loaded. This work makes that recovery and visibility
repeatable before additional sources expand the warehouse.

## Capabilities

- **CAP-1**
  - **intent:** An approved source transfer can recover from a temporary failure at an equivalent official endpoint without losing or overwriting retained evidence.
  - **success:** A test shows an ACS artifact retry uses an explicit official fallback only after the primary returns a retryable non-data response, and the retained artifact records its actual URL and checksum.
- **CAP-2**
  - **intent:** An operator can view a source’s intended coverage, retained artifacts, failures, and published records in one report.
  - **success:** A status command reports those four states for ACS/AHS and distinguishes planned, downloaded, failed, staged, and published work.
- **CAP-3**
  - **intent:** A new source can declare its selection, resource limits, provenance rules, and lifecycle state in the same reviewed shape.
  - **success:** Existing ACS/AHS contract and one established bulk-source contract validate against the common shape without moving actual artifact state out of the database ledger.

## Constraints

- YAML is the human-reviewed contract; the database artifact ledger is the factual record of URLs, retained bytes, checksums, versions, and states.
- Original government endpoints remain the evidence source. An alternate URL is allowed only when it is explicitly verified as an equivalent government-published object.
- Unknown sizes, content-type mismatches, capacity failures, and non-equivalent fallbacks fail closed.
- A retry must reuse verified retained artifacts and never overwrite evidence.
- The work uses Connectors; it does not add source-specific central-dispatch branches.

## Non-goals

- Replacing official evidence with a third-party mirror or an IPUMS extract.
- A single giant registry that duplicates the artifact ledger.
- Adding new substantive datasets before the current transfer is recoverable and observable.

## Success signal

The ACS transfer can resume after the demonstrated endpoint failure, and an
operator can run one report to see its contract, retained bytes, failure reason,
and loading state. The same contract/status pattern is ready for the next
Connector without a special case.
