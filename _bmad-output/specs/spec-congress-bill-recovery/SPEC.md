---
id: SPEC-congress-bill-recovery
companions:
  - recovery-evidence.md
  - representation-fallback-boundary.md
  - ../../../docs/PROJECT-STATE.md
  - ../../planning-artifacts/research/technical-official-fallback-sources-for-congress-g-2026-09-29/research.md
sources:
  - ../../../docs/SESSION-HANDOFF-2026-09-27.md
  - ../../../docs/NEXT-SESSION-PROMPT.md
---

> **Canonical contract.** This SPEC and its companions define the bounded recovery for five Congress.gov publisher failures. They do not authorize another 106–107 bill download.

# Congress.gov bill recovery

## Why

Congress.gov still fails on five known endpoints, leaving two otherwise available 107th Congress bills absent and three saved bills without cosponsor evidence. The warehouse needs to preserve the official data that is available while making the unavailable data visible and retryable rather than inventing a complete record or re-running a large acquisition.

## Capabilities

- **CAP-1**
  - **intent:** The warehouse can retain H.R. 2842 and H.R. 2843 as explicitly partial official records when their detail endpoint is unavailable.
  - **success:** Each record uses the official bill-list entry for identity, title, introduction date, and latest action; retains every successful child response with its own provenance; records the failed detail URL; and does not supply a sponsor or policy area unless an official response provides it.

- **CAP-2**
  - **intent:** The operator can retry only the five named failed endpoints after Congress.gov repairs them.
  - **success:** A narrow command or selector requests only those endpoints, leaves immutable evidence untouched, upgrades a partial bill only after a successful detail response, and reports what remains unavailable.

- **CAP-3**
  - **intent:** The operator can tell partial recovery from source completion.
  - **success:** Run results, the source tracker, and the project handoff name H.R. 2842, H.R. 2843, S. 1378, S.Res. 218, and H.R. 5346 as publisher-side gaps until their respective endpoint succeeds.

- **CAP-4**
  - **intent:** The operator can distinguish a failed canonical API component from separately retained official corroboration.
  - **success:** No corroborating representation can populate a canonical detail or cosponsor field without an approved field-equivalence contract; a later API response reconciles the gap without deleting historic evidence.

## Constraints

- Use only original, authenticated Congress.gov API responses; the public website's bot challenge and legacy caches are not fallback evidence.
- Retain original bytes immutably, with URL, checksum, and artifact lineage for every promoted fact. A failed endpoint is an artifact failure, never a fabricated JSON response.
- Do not rerun the full 106–107 sync, name-match people, or infer cosponsors from other records.
- The two list-derived rows are partial, not complete: missing fields remain null and source-member labels identify their actual evidence.
- A future alternate representation must retain its own URL, retrieval metadata,
  content type, checksum, source member, and field-equivalence contract. It is
  never relabelled as failed Congress.gov API bytes.

## Non-goals

- This does not solve Congress.gov's underlying MemberTerm publisher errors.
- This does not fill the three cosponsor lists from unofficial mirrors, historic local files, or a person-name match.
- This does not automatically substitute Congress.gov public HTML, GovInfo BILLS,
  or GovInfo History of Bills for a canonical detail or cosponsor component.
- This does not start new legislative sources, rework committee-assignment verification, or change the completion bar in `legislative-north-star.md`.

## Success signal

The two missing bills are auditable partial rows built only from available official responses, while the three unavailable cosponsor lists and both missing detail pages remain plainly reported and can be retried in isolation. A later successful endpoint replaces only the corresponding gap with new evidence; any future corroborating representation remains separate until its field-level contract is approved.
