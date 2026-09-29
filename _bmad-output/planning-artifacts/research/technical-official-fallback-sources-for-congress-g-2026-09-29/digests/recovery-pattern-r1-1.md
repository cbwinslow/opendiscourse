# Recovery-pattern official-source digest — round 1

Accessed: 2026-09-29. Researcher received no project context.

- **A 500 response is not proof a record is absent** (high confidence).
  RFC 9110 defines it as an unexpected server condition that prevented
  fulfillment. Bounded retries are appropriate for idempotent GET requests;
  honor `Retry-After` when present. The RFC does not require exponential
  backoff or say every 500 is temporary. Source:
  [IETF RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html), June 2022.
- **A recovery must retain an attempt chain and preserve successful bytes only**
  (high confidence as an evidence-supported design inference). Record logical
  resource key, request identity, timestamps, status/headers, error body
  fingerprint, retry policy/delay, final outcome, response checksum/bytes/type,
  and any fallback relation. Do not convert a 500 into an empty or absent
  record. Sources: [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html),
  [Library of Congress dataset preservation guidance](https://www.loc.gov/preservation/resources/rfs/data.html),
  and [Library of Congress METS overview](https://www.loc.gov/standards/mets/METSOverview.v2.html).
- **An official fallback representation is distinct evidence, not the failed
  endpoint's bytes** (high confidence as a design inference). It needs a
  documented equivalence rule and its own URL/checksum; otherwise leave the
  resource unresolved/partial. This follows the Library's guidance to preserve
  canonical URLs, publisher/version information, checksums, and manifests.
