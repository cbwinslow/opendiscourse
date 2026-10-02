# OpenStates source mapping and completion contract

This companion defines the mapping review required by `SPEC-openstates-political-core` before bulk promotion. It is a contract for an owned OpenDiscourse model, not a request to copy the OpenStates database.

## Source boundary

The initial source is the full read-only `openstates_source` FDW snapshot. Its current political tables include `opencivicdata_person`, `personidentifier`, `organization`, `jurisdiction`, `legislativesession`, `bill`, `billaction`, `billsponsorship`, `voteevent`, and `personvote`. The snapshot's physical tables are evidence interfaces only: an upstream upgrade can change them.

Every run must save a source fingerprint containing the snapshot artifact identity/checksum, source database version when available, table-and-column manifest, row counts, and the mapping version. The promotion must stop when that fingerprint differs from the reviewed baseline, unless a migration explicitly approves the change.

## External-model crosswalk

The external projects below are references for a specific decision, not database dependencies or replacement evidence. This is the reason OpenDiscourse keeps the civic model and adapts provider data instead of cloning an application database.

| Reference | What it establishes | OpenDiscourse decision |
| --- | --- | --- |
| [OpenStates data model](https://docs.openstates.org/data/) and [OCD people/posts/memberships proposal](https://open-civic-data-docs.readthedocs.io/en/latest/proposals/0005.html) | Jurisdiction, session, organization, person, post, membership, bill, and vote form a practical U.S. legislative vocabulary. | Adopt these concepts and preserve OCD IDs; do not expose upstream Django tables as the stable contract. |
| [Popolo specification](https://www.popoloproject.com/specs/) | A post exists independently of its holder; membership expresses the dated relationship. It also defines people, organizations, areas, motions, vote events, and votes. | Keep `post` separate from `membership`, retain dates and division history, and use typed vote relations. |
| [django-popolo](https://github.com/openpolis/django-popolo) | A reusable physical implementation can add application-specific models and undergo breaking changes while keeping the conceptual standard. | Treat standards as semantic guidance, not as a frozen foreign physical schema. |
| [GovTrack setup](https://github.com/govtrack/govtrack.us-web/blob/main/README.md) and [unitedstates/congress](https://github.com/unitedstates/congress) | Federal collection output can be separate from the application database and then parsed into owned models. | Wrap/consume official federal acquisition outputs, retain evidence, and promote into shared canonical tables. |
| [congress-legislators](https://github.com/unitedstates/congress-legislators) | Historical federal people records include cross-source identifiers and dated terms. | Use BioGuide as the federal person join key and retain other IDs as assertions; never use a display-name join. |
| [Voteview member votes](https://www.voteview.com/articles/data_help_votes) | Researchers benefit from a narrow member × roll-call analytical grain with a durable external member identifier. | Publish a derived `member_vote` mart over canonical facts; do not replace source roll-call evidence with an analytical extract. |
| [CongressData](https://github.com/ippsr/CongressData) | Research panels need variable-level descriptions, temporal coverage, sources, and citations. | Every mart measure declares its source, period, formula, coverage, and evidence path. |
| [LegiScan API client](https://api.legiscan.com/docs/) | Production legislative ingestion can use a database schema/ERD and bulk-update workflow. | Study change-feed and bulk-import mechanics only; do not adopt its schema or treat its commercial data as canonical evidence. |

This crosswalk supports a stable *conceptual* model. It does not promise that any upstream source's implementation, availability, licenses, or table layout will remain unchanged. The source fingerprint, field inventory, and Connector boundary remain mandatory.

## Canonical mapping

| Source concept | Owned researcher contract | Required treatment |
| --- | --- | --- |
| Jurisdiction and division | `core.jurisdiction`, geographic/division reference | Preserve OCD/source identifier, classification, name, URL, parent/division reference, update timestamps, and source detail. |
| Legislative session | `core.legislative_session` | Preserve source key, jurisdiction, identifiers, dates, class, active status, evidence, and source detail. |
| Organization and its hierarchy | `core.organization`, `core.organization_identifier` | Preserve source key, class, name, jurisdiction, parent relationship, links, sources, other names, and source detail. |
| Person and identifiers | `core.person`, `core.person_identifier`, name assertions | Preserve source key and every external identifier; type usable names, biography/dates/party/contact fields where approved, retain the source record, and never resolve a person by name. |
| Office/post and membership | `core.post`, `core.membership` | Represent an office separately from its holder; preserve organization, division/district, role, party, dates, contact/leadership detail, and source key/evidence. If a required source relation is absent, report coverage rather than invent it. |
| Bill, action, sponsorship, committee, subject, citation, document | `core.bill` and normalized bill child tables | Preserve OCD ID, official identifier, session/organization, class, dates, classification, subjects/citations, ordering, sponsor type/primary flag, source documents, and source detail. A source reference must remain source-keyed even when the target is not yet promoted. |
| Vote event and individual vote | `core.roll_call`, `fact.member_vote`, supporting vote totals/source rows | Preserve source key, motion/question, classifications, result, timing/order, organization/session/bill/action references, vote option/note/voter text, and source detail. Unresolved voters remain recorded as source-native unresolved rows, never name-linked. |

## Field-disposition inventory

Before promoting more than a bounded pilot, the Connector must generate and version a machine-readable inventory for every discovered scalar column and every public nested JSON/array key. Each row must include:

`source_table`, `source_path`, `source_type`, `null_rate`, `sample_count`, `source_key`, `disposition`, `owned_target`, `transform`, `loss_risk`, `reason`, `mapping_version`, and `reviewed_at`.

Allowed dispositions are:

| Disposition | Meaning | Rule |
| --- | --- | --- |
| `typed_searchable` | A field becomes an indexed/typed owned attribute or relation. | Include source evidence and a reconciliation rule. |
| `retained_source_detail` | The field remains in a source-record payload because it is useful but not a stable shared attribute. | Preserve verbatim structure and source key; document why it is not promoted. |
| `excluded` | The field is intentionally not retained in the research contract. | Require a specific reason: duplicate evidence, non-public/unsafe content, transient operational value, or confirmed upstream implementation-only field. |

`excluded` is exceptional. Upstream timestamps, source keys, `extras`, links, source citations, other names, classifications, arrays, and nested objects are not allowed to disappear merely because they do not fit a first-pass typed table.

## Identity and federal/FEC connections

The source's person ID is valid only within its provider namespace. It may anchor provenance and an OpenStates identity assertion, but it is not evidence that a same-named federal person or FEC candidate is the same human.

| Connection | Permitted key | Gate |
| --- | --- | --- |
| OpenStates to OpenDiscourse person | OpenStates/OCD person identifier | Provenance-backed source assertion. |
| Federal member to OpenDiscourse person | BioGuide identifier | Existing federal identity rules. |
| FEC candidate/committee to person | Reviewed identifier bridge plus configured `person_join` | Must call `identitygate.require_person_join`; FEC remains native/unresolved until enabled. |
| Geographical connection | Versioned geographic identifier and valid dates | Never substitute a present-day boundary for a historical one. |

## Coverage and reconciliation

The promoted model must distinguish **available in the source**, **retrieved in this snapshot**, **validly promoted**, **unresolved**, and **not supplied**. It must publish counts for each source table/entity, jurisdiction, session, and available date range. A zero count is not evidence of a real-world zero unless the source declares coverage.

Each promotion run must reconcile:

1. source rows selected versus accepted, rejected, deferred, and promoted rows;
2. source IDs versus owned identifier/source-record rows;
3. foreign references versus resolved and unresolved targets;
4. source field inventory versus approved mapping version; and
5. evidence artifacts/payloads versus every final promoted row.

## Definition of done for Story 1

Story 1 is complete only when all of the following evidence exists:

1. The generated source table/column/nested-field inventory covers the actual snapshot and records a disposition for every field.
2. The mapping is reviewed against current OpenDiscourse tables and identifies minimal schema changes, including why each is needed; no source-table copy is proposed.
3. The mapping explicitly covers people, organizations, jurisdictions, sessions, offices/posts, memberships, bills, actions, sponsors, documents, vote events, and individual votes; absent source coverage is reported as a gap.
4. A source fingerprint and drift test fail closed for an unreviewed new table, column, or nested public field.
5. Identity tests prove that a display-name collision does not create a cross-provider link, while a permitted identifier does.
6. The design documents exact reconciliation metrics, restart/idempotency behavior, provenance requirements, and a bounded pilot before any broad promotion.
7. `just check-fast` passes after the contract artifacts and any supporting code/tests are added. A database check is required once a migration or database query is introduced.

## Implementation order

1. Generate the inventory and coverage report from the current read-only source snapshot.
2. Review the inventory and write the minimal owned-schema migration proposal.
3. Implement a bounded, provenance-backed promotion pilot and its reconciliation tests.
4. Review pilot evidence, then approve jurisdiction/session batches separately.
5. Only after political identities are proven, evaluate downstream FEC/federal research marts.
