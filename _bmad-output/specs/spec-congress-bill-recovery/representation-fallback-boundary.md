# Representation fallback boundary

This companion governs a future representation fallback; it does not authorize
one to load data today. The current recovery remains the five named canonical
Congress.gov API paths.

| Representation | Permitted use now | Forbidden use |
|---|---|---|
| Congress.gov authenticated JSON API | Canonical bill/detail/cosponsor evidence and promotion | None beyond the existing bounded recovery contract |
| Congress.gov public HTML | No automated acquisition or promotion; it is the same publisher system and may share the outage | Calling it independent evidence or a replacement API |
| GovInfo BILLS package | Manual corroboration of a published bill version or text | Filling bill-detail actions/metadata or a complete cosponsor component |
| GovInfo History of Bills | Manual corroboration of historical publication/index references | Inferring a complete identifier-backed cosponsor list, dates, or withdrawals |

An implementation can admit a new representation only after a reviewed source
contract names the exact logical component and fields, documents why the
representation is equivalent for those fields, and defines reconciliation when
the canonical API recovers. Each retained response remains its own immutable
artifact with URL, retrieval metadata, content type, checksum, and source
member. A fallback never masquerades as bytes from a failed API endpoint.

The controlled 2026-09-29 check found all five canonical paths still return
HTTP 500 through the API intermediary. A browser cache clear cannot repair that
service path. See the adopted research report for its source evidence and run
ledger.
