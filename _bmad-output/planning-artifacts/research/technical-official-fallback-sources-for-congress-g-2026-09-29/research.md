---
title: 'Technical research: official fallback sources for Congress.gov 107 bill and cosponsor recovery'
type: 'technical'
topic: 'Official fallback sources for Congress.gov 107 bill and cosponsor recovery'
decision: 'Whether OpenDiscourse should add an official fallback source for temporary Congress.gov bill-detail and cosponsor failures, and what reusable recovery design preserves provenance.'
source: 'Native official-source web research'
status: complete
preset: standard
validation: normal
verified_claims: 3
unverified_claims: 0
created: '2026-09-29'
updated: '2026-09-29'
---

# Technical research: official fallback sources for Congress.gov 107 bill and cosponsor recovery

## Executive summary

**Do not replace the missing Congress.gov 107th-Congress detail and cosponsor
responses with GovInfo data automatically.** GovInfo's structured Bill Status
data begins at the 108th Congress, so no like-for-like 107th record exists
there. Its individual bill publications and History of Bills are valuable
official corroborating evidence, but the cited documentation does not
establish field-level equivalence to the Congress.gov cosponsor response.
[1][2][3]

The safe reusable design is a bounded recovery workflow: retry the canonical
Congress.gov API record; retain a partial bill only if official evidence was
successfully acquired; then leave the failed component explicitly unresolved. An
emergency Congress.gov public-HTML representation can be added only as a
separately labelled, same-publisher representation and reconciled when the
API recovers. This is a project provenance policy, not a claim that HTML is
an independent authority. HTTP 500 means a server failure, not that the bill
or cosponsor data is absent. [4]

The biggest caveat is practical: the historical GovInfo material may help a
human verify a bill or a particular printed cosponsor reference, but it is
not a safe source for filling the three failed canonical cosponsor records.

## Recommendations

1. **Keep the five identified failures bounded and unresolved today:** 107th
   Congress H.R. 2842 and H.R. 2843 detail pages; 106th Congress S. 1378 and
   S.Res. 218 cosponsor pages; and 107th Congress H.R. 5346 cosponsor page.
   Do not use GovInfo to fill their canonical components. High confidence: the
   relevant structured GovInfo collection does not cover Congress 107. [1]
2. **Design one representation-fallback extension before implementing it.**
   It should support an explicit per-component equivalence contract, immutable
   evidence, bounded retries, and reconciliation. High confidence in the
   coverage limitation; medium confidence that public HTML will be operationally
   useful because it is the same publisher system.
3. **Use GovInfo BILLS/HOB only as cited manual corroboration until a field
   contract proves otherwise.** High confidence: HOB documentation says a
   typical entry includes sponsor and cosponsor names, but the cited sources do
   not guarantee that for every bill package or entry. [2][3]

## Official-source coverage

Congress.gov API v3 is the Library of Congress's documented machine interface
for a bill detail record and its cosponsors. The documented routes are
`/bill/{congress}/{billType}/{billNumber}` and its `/cosponsors` child. [5]
Congress.gov replaced THOMAS, which was retired in 2016; THOMAS is therefore
not available as a live fallback service. [6]

GovInfo fills a narrower role. Its Developer Hub documents structured
Congressional Bill Status from Congress 108 forward, excluding Congress 107.
[1] Its Congressional Bills collection includes published bill versions from
Congress 103 forward, while its BILLS bulk XML begins at Congress 113; early
availability must not be described as machine-readable XML. [2] GovInfo's
History of Bills covers 1983 onward and includes sponsor/cosponsor references
and actions, but is a publication/index representation rather than a
bill-status record. [3] The cited documentation does not establish that either
GovInfo representation is field-level equivalent to Congress.gov's cosponsor
response.

## Recommended recovery architecture

Keep the current logical resource key—Congress, bill type, bill number, and
component—as the stable identity. Put source-specific acquisition in small
provider/representation adapters, not in command dispatchers or the database
promotion code:

1. **Canonical API adapter:** acquire the documented Congress.gov JSON route.
   On a successful response, retain the bytes and promote only fields the
   JSON contract supports.
2. **Failure ledger:** for each failed GET, record the request URL, time,
   status, relevant headers, bounded retry policy, and error-body fingerprint.
   Keep its component `unresolved`; never translate a 500 into a missing or
   empty source record. RFC 9110 defines 500 as an unexpected server condition
   that prevented fulfillment. [4]
3. **Representation adapters, not field substitution:** an approved
   `CongressGovHtmlRepresentation` may retain public HTML from the same
   Library of Congress publication system for a specified bill page. A
   `GovInfoBillPublicationRepresentation` may retain an individual bill
   package or HOB item for document-level corroboration. Neither adapter may
   claim it supplied a canonical complete cosponsor list unless a separate
   source contract proves field-level equivalence. The public HTML is not an
   independent authority, may share the API outage, and is not a documented
   public API.
4. **Evidence-first promotion:** each promoted row retains the representation's
   own URL, retrieval time, content type, checksum, and source-artifact
   identity. The fallback relation is explicit rather than pretending the
   failed API supplied those bytes. This is an OpenDiscourse design decision
   supported by Library of Congress preservation guidance on canonical URLs,
   publisher/version information, checksums, and manifests. [7]
5. **Reconciliation:** when the API route succeeds later, retain it as new
   evidence and compare fallback-derived fields with the API fields. Prefer the documented API
   for the canonical component; preserve the earlier fallback as evidence and
   report disagreements rather than overwriting history.

This keeps recovery reusable: the generic lifecycle owns retry state,
artifacts, and reconciliation; adapters own only source URL construction and
parsing. It avoids a source-specific `if/elif` in a CLI command or a generic
"fallback means equivalent" shortcut.

## Open questions

- Does the public Congress.gov HTML route return reliably when the equivalent
  API component fails? This needs a bounded live operational probe after the
  publisher recovers; do not test it by repeatedly hitting failed pages now.
- Which exact bill fields, if any, can an individual 107th GovInfo BILLS
  package prove equivalent to the Congress.gov detail schema? That requires a
  field-by-field contract and fixtures, not a coverage assertion.

## Source appendix

| Ref | Finding supported | Publisher | Publication / update | Accessed | Confidence |
|---|---|---|---|---|---|
| [1] | BILLSTATUS begins at Congress 108 | [U.S. Government Publishing Office Developer Hub](https://www.govinfo.gov/developers) | Not shown | 2026-09-29 | High |
| [2] | BILLS bulk XML starts at 113; published bills cover 103 onward; early formats are not universally XML | [U.S. Government Publishing Office BILLS XML user guide](https://www.govinfo.gov/bulkdata/BILLS/resources/BILLS-XML_User-Guide-v2.pdf) | Not shown | 2026-09-29 | High |
| [3] | History of Bills coverage and content | [U.S. Government Publishing Office HOB help](https://www.govinfo.gov/help/hob) | Updated 2024-03-11 | 2026-09-29 | High |
| [4] | Meaning of HTTP 500 and GET semantics | [IETF RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html) | 2022-06 | 2026-09-29 | High |
| [5] | Congress.gov documented bill and cosponsor endpoints | [Library of Congress Congress.gov API OpenAPI document](https://github.com/LibraryOfCongress/api.congress.gov/blob/main/Documentation/openapi.json) | Current main branch | 2026-09-29 | High |
| [6] | THOMAS retirement and transition to Congress.gov | [Library of Congress announcement](https://www.loc.gov/item/prn-16-004/thomas-gov-to-retire-july-5/2016-04-28/) | 2016-04-28 | 2026-09-29 | High |
| [7] | Preservation metadata expectations for datasets | [Library of Congress Recommended Formats Statement: Datasets](https://www.loc.gov/preservation/resources/rfs/data.html) | Not shown | 2026-09-29 | Medium |

## Staleness map

Recheck Congress.gov and GovInfo coverage/API claims by 2027-09-29, or earlier
if either publisher announces coverage changes. Revisit the HTTP reference if
the project retry policy or applicable standard changes.
