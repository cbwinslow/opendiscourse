# Recovery evidence and implementation boundary

## Read-only audit — 2026-09-27

| Endpoint group | 107 H.R. 2842 | 107 H.R. 2843 | 106 S. 1378 | 106 S.Res. 218 | 107 H.R. 5346 |
|---|---:|---:|---:|---:|---:|
| Bill detail | 500 | 500 | 200 | 200 | 200 |
| Actions, committees, subjects, summaries, text | 200 each | 200 each | 200 each | 200 each | 200 each |
| Cosponsors | 200 (empty list) | 200 (empty list) | 500 | 500 | 500 |

`https://www.congress.gov/` displayed its Cloudflare human-verification page to the automated browser for a missing-detail and a missing-cosponsor bill. It is not usable as evidence in this environment.

The official 107th Congress bill-list page at offset 4000 contains both missing bills:

| Bill | Introduced | Latest action | List-supplied fields that may be promoted |
|---|---|---|---|
| H.R. 2842 | 2001-09-05 | 2001-10-31 — Referred to the Subcommittee on Benefits. | Congress, type, number, title, introduced date, latest action |
| H.R. 2843 | 2001-09-05 | 2001-09-10 — Referred to the Subcommittee on Crime. | Congress, type, number, title, introduced date, latest action |

The list does not expose sponsors or policy area. The partial path must not create values for either.

## Required implementation behavior

1. Retain the list response and each successful child response as separate immutable artifacts. The partial bill's base row uses only values in the list row; promoted child facts use their child artifact, not the list artifact.
2. Record the failed detail endpoint using the existing failed-artifact path and label the resulting run/target partial.
3. Use a distinct source-member value for the list-derived base record, so the evidence says `list`, not `detail`. Preserve the raw list row in `core.bill_source_record` or another existing evidence-backed record keyed to its list artifact.
4. A narrow recovery entry point accepts exactly the known bill/part keys (or a checked-in manifest of them). It must not enumerate all bills or treat a partial bill as complete.
5. When detail later returns 200, retain it and use normal detail-based assembly to update the base row. Do not delete historic evidence. When a cosponsor endpoint later returns 200, promote only that official response.

## Tests and verification

- Parser tests cover construction from a list row; invalid or incomplete list identities fail.
- Connector tests prove an HTTP 500 detail plus successful children saves a partial row, does not add sponsor/policy-area values, and leaves it retryable.
- Connector tests prove the three cosponsor 500s keep their existing bills, create failed evidence, and never create inferred sponsorships.
- Idempotency and resume tests prove a second narrow retry does not overwrite retained bytes, and successful recovery does not duplicate base or child facts.
- Run the fast gate and the focused database tests. Use one disposable or cleaned-up test database; do not modify the live port-5434 data during verification.
