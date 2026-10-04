# OpenStates source mapping and completion contract

This companion defines the mapping review required by `SPEC-openstates-political-core` before bulk promotion. It is a contract for an owned OpenDiscourse model, not a request to copy the OpenStates database.

The canonical tables model civic and political entities. A provider identifier describes how Congress.gov, GovInfo, the House, the Senate, OpenStates, or a later source names that entity. OpenDiscourse keeps the owned id. The provider id stays in a namespaced identifier row, with the artifact or payload and the run that asserted it.

## Source boundary

The source of record is the full restored OpenStates snapshot; `openstates_source`
is its least-privilege, read-only FDW reader. The current FDW may expose only a
reviewed subset of the snapshot's relations. Story 1 must inventory the restored
snapshot relation manifest **and** the FDW allow-list, then account for every
relation missing from the FDW before calling the inventory complete. The
snapshot's physical tables are evidence interfaces only: an upstream upgrade can
change them.

Every run must save a source fingerprint containing the snapshot artifact
identity/checksum, source database version when available, **relation** and
table-and-column manifest, row counts, FDW exposure status, and mapping version.
The promotion must stop when that fingerprint differs from the reviewed baseline,
unless a migration explicitly approves the change.

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
| Organization and its hierarchy | `core.organization`, `core.organization_identifier` | Preserve source key, class, name, jurisdiction, and an owned parent link (legislature, chamber, committee, subcommittee). Jurisdiction, division, and geography stay separate. Do not store an OCD id in `jurisdiction_geoid`. |
| Person and identifiers | `core.person`, `core.person_identifier`, name assertions | A person is found by BioGuide, an OpenStates/OCD person id, or another approved identifier. The same person may carry both when each identifier is an authoritative assertion. Never merge on name, party, district, or office. |
| Office/post and membership | `core.post`, `core.membership` | A post exists without a holder. Membership is the dated link among person, organization, post, and division. Historical facts use the division and boundary vintage of that time. |
| Bill, action, sponsorship, committee, subject, citation, document, version | `core.bill`, `core.bill_identifier`, and normalized child tables | Owned `bill_id`, jurisdiction, session, originating organization where supplied, official identifier, classifications, and dates identify a bill. Congress keeps Congress number, bill type, and bill number. OpenStates keeps its bill id and the exact official identifier, such as `HB 264`. That identifier is not a title and is not parsed into federal type and number. |
| Vote event and individual vote | `core.roll_call`, a namespaced roll-call identifier, `fact.member_vote`, source totals | Federal roll numbers and OpenStates vote ids stay in their own namespaces. An unresolved voter stays in source evidence with the displayed name and position. No canonical member vote is inserted without a resolved person, and source totals still reconcile the roll call. |

## Relation and field-disposition inventory

Before promoting more than a bounded pilot, the Connector must generate and
version a machine-readable **relation inventory** for every source relation in
the restored snapshot. Each relation must be marked `promote_typed`,
`retain_source_only`, `excluded`, or `unavailable_in_snapshot`, with a reason,
FDW exposure status, and any required FDW expansion proposal. A relation that is
not in the current FDW is not an implicit exclusion.

The field inventory then covers every discovered scalar column and every public
nested JSON/array key of each relation marked `promote_typed` or
`retain_source_only`. Each field row must include:

`source_table`, `source_path`, `source_type`, `null_rate`, `sample_count`, `source_key`, `disposition`, `owned_target`, `transform`, `loss_risk`, `reason`, `mapping_version`, and `reviewed_at`.

Allowed dispositions are:

| Disposition | Meaning | Rule |
| --- | --- | --- |
| `typed_searchable` | A field becomes an indexed/typed owned attribute or relation. | Include source evidence and a reconciliation rule. |
| `retained_source_detail` | The field remains in a source-record payload because it is useful but not a stable shared attribute. | Preserve verbatim structure and source key; document why it is not promoted. |
| `excluded` | The field is intentionally not retained in the research contract. | Require a specific reason: duplicate evidence, non-public/unsafe content, transient operational value, or confirmed upstream implementation-only field. |

`excluded` is exceptional. Upstream timestamps, source keys, `extras`, links,
source citations, other names, classifications, arrays, and nested objects are
not allowed to disappear merely because they do not fit a first-pass typed table.
The same rule applies to whole entities: bill versions, abstracts, related-bill
relations, vote counts, events, agendas, participants, media, documents, office
records, and any other discovered source relation need an explicit disposition.

## Identity and federal/FEC connections

The source's person ID is valid only within its provider namespace. It may anchor provenance and an OpenStates identity assertion, but it is not evidence that a same-named federal person or FEC candidate is the same human.

| Connection | Permitted key | Gate |
| --- | --- | --- |
| OpenStates to OpenDiscourse person | OpenStates/OCD person identifier | Provenance-backed source assertion. |
| Federal member to OpenDiscourse person | BioGuide identifier | Existing federal identity rules. |
| FEC candidate to person | Reviewed candidate identifier bridge plus configured `person_join` | Must call `identitygate.require_person_join`; FEC remains native/unresolved until enabled. |
| FEC committee to person | Never permitted | A committee is FEC-native/organization data, not a person identifier. Candidate-to-committee linkage remains a separate evidence-backed relation. |
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

1. The generated source-relation/table/column/nested-field inventory covers the actual snapshot and records a disposition for every relation and field. It compares the snapshot manifest with the FDW allow-list and accounts for every difference.
2. The mapping is reviewed against current OpenDiscourse tables and identifies minimal schema changes, including why each is needed; no source-table copy is proposed. The semantic decisions in "Approved semantic decisions" were accepted on 2026-10-04. That acceptance does not sign each field, attest the restored archive, or authorize a migration.
3. The mapping explicitly covers people, organizations, jurisdictions, sessions, offices/posts, memberships, bills, actions, sponsors, documents, vote events, individual votes, and every additional discovered relation; absent source coverage is reported as a gap.
4. A source fingerprint and drift test fail closed for an unreviewed new relation, table, column, or nested public field.
5. Identity tests prove that a display-name collision does not create a cross-provider link, while a permitted identifier does.
6. The design documents exact reconciliation metrics, restart/idempotency behavior, provenance requirements, and a bounded pilot before any broad promotion.
7. `just check-fast` passes after the contract artifacts and any supporting code/tests are added. A database check is required once a migration or database query is introduced.

## Required Story 1 audit outputs

Story 1 is a read-only audit. It produces no migration, FDW alteration,
source-database write, canonical promotion, FEC transfer, or person join. Its
versioned outputs are:

| Output | Required contents |
| --- | --- |
| Snapshot inventory | Every restored relation; columns; nested JSON/array paths; row counts; null rates; candidate keys; date ranges; jurisdictions; and representative samples safe for review. |
| FDW coverage diff | Snapshot relation manifest versus `openstates_source` allow-list, including every present-but-unreadable relation. The audit proposes no reader change. |
| Entity-disposition matrix | One disposition for every source relation: `promote_typed`, `retain_source_only`, `reference_only`, `implementation_only`, `excluded`, or `unavailable_in_snapshot`, with an evidence-backed reason. |
| Field-disposition matrix | For every public field in a promoted/retained relation: typed target or retained treatment, transform, source key, loss risk, null rate, and mapping version. |
| Coverage report | Jurisdiction × entity × session/time range, distinguishing `available`, `present_in_snapshot`, `readable_via_fdw`, `mapped`, `unresolved`, and `not_supplied`. |
| Snapshot fingerprint | Artifact/checksum plus schema/relation/table/column fingerprint, row counts, and FDW exposure so a changed dump fails closed. |
| Identity audit | OpenStates identifier namespaces, BioGuide availability/uniqueness, and unresolved identifiers; it measures but does not create cross-provider links. |
| Reconciliation baseline | Source counts, keys, and unresolved-reference counts that Story 3 must reproduce or explain for each promoted grain. |

The audit's final answer is: what is in the snapshot, what can currently be
read, how each source relation/field is treated, and which narrowly scoped
reader or schema changes would be required before promotion. Those later changes
are separate checkpointed stories.

## Implementation order

1. Generate the snapshot relation/field/coverage report and compare it with the current read-only FDW allow-list.
2. Review every missing FDW relation: propose a least-privilege reader expansion or record an explicit non-promotion disposition, then write the minimal owned-schema migration proposal.
3. Implement a bounded, provenance-backed promotion pilot and its reconciliation tests.
4. Review pilot evidence, then approve jurisdiction/session batches separately.
5. Only after political identities are proven, evaluate downstream FEC/federal research marts.

## Approved semantic decisions (2026-10-04)

Accepted for the later schema story. They do not authorize a migration, a reader change, a source write, promotion, an FEC transfer, or a person join. Issue #100 stays a read-only audit. `docs/audits/openstates/2026-10-02/mapping-review.json` remains a field proposal: `approved` is false and no field has `reviewed_at`.

Providers are peers. Congress.gov, GovInfo, the House, the Senate, and OpenStates each keep their own files and identifiers. Those identifiers become assertions on owned rows. Neither the OpenStates Django tables nor today's Congress-shaped columns are the warehouse schema.

1. **Bills.** A bill is an owned `bill_id` plus jurisdiction, legislative session, originating organization where the source supplies one, the official identifier, classifications, dates, and identifier assertions. Congress rows keep Congress number, federal bill type, and federal bill number. OpenStates rows keep the OCD bill id, the exact official identifier (`HB 264`), jurisdiction, session, chamber where supplied, classifications, and source detail. Do not invent federal `bill_type` or `bill_number` for a state bill. `HB 264` is an official identifier in `core.bill_identifier`, not a title.
2. **Sessions.** Keep the owned UUID primary key. Session identity is jurisdiction-scoped. Store the provider session identifier beside the jurisdiction and the evidence. Do not use an OpenStates id as the physical primary key.
3. **Organizations.** Represent legislature, chamber, committee, and subcommittee with an owned parent link. Keep external ids in `core.organization_identifier`. `jurisdiction_geoid` is geography only. Organization identity, jurisdiction, division, and geography stay separate.
4. **People.** Federal people resolve on BioGuide. OpenStates people enter on their OCD person id. Both may name the same `core.person` only when each side is an authoritative identifier assertion. Never merge on name, party, district, or office. `core.person_identifier(namespace, external_id)` remains the identity mechanism.
5. **Sponsorship.** Federal sponsors keep namespace `bioguide`. OpenStates sponsors use the OCD person-id namespace. A name with no stable id stays unresolved source evidence. Do not invent a person. Keep sponsor/cosponsor, the primary flag when the source supplies it, and useful source order. Unusual wording stays in the source record. The role check is not a place to store every provider sentence.
6. **Documents and bill versions.** `document_id` is owned. An OpenStates document id is a namespaced identifier, not the primary key. Link documents to bills through `core.bill_document`. Bill versions, abstracts, documents, media, related bills, vote counts, events, and agendas each keep an explicit disposition. Do not fold an OpenStates version into GovInfo's `version_code`. `congress`, `bill_type`, `bill_number`, and `version_code` are federal metadata, not the definition of a document.
7. **Roll calls.** `roll_call_id` is owned. A federal roll number and an OpenStates vote id are different namespaces. Never write an OpenStates vote id into `roll_number`. Prefer `core.roll_call_identifier`, on the same pattern as person, bill, and organization identifiers, over one un-namespaced `external_id`. Source totals stay even when a voter is unresolved.
8. **Individual votes.** `fact.member_vote` is only for a resolved person, keyed by `(roll_call_id, person_id)`. An unresolved voter keeps the source record, the displayed name, the position, and the evidence. Do not insert a member vote with a null person, do not name-match, and do not invent a person. The reconciliation report must count those rows. Aggregate totals still reconcile the roll call.
9. **Field preservation.** Every discovered relation and public field gets a disposition: typed/promoted, retained source detail, reference-only, implementation-only, unavailable, or excluded with a reason. A field that does not fit the first typed columns is retained, not dropped.
10. **Posts, memberships, and geography.** A post is not a membership. Membership is the dated relationship. Historical facts use the division and boundary of that date, not today's district.
11. **Source boundary.** Database `openstates` is replace/restore only. `openstates_source` is the least-privilege read interface. Researchers query owned tables. A later dump restore must be able to replace `openstates` without changing owned political rows.
12. **Provenance.** External ids are kept beside owned UUIDs. A promoted row points at its artifact or payload, member path where the source has one, mapping version, and ingest run. Conflicts stay visible.

## Schema mismatches the later story must fix

Reviewed against `src/opendiscourse_research/models/core.py` on 2026-10-04. No table was changed.

| Current shape | Why it is federal-first | Required future change |
| --- | --- | --- |
| `core.bill.bill_type` and `bill_number` are `NOT NULL`. Uniqueness is `(jurisdiction, legislative_session, bill_type, bill_number)`. `sql/query/legislation/upsert_bill.sql` reloads on that exact key. | A state bill has no Congress type or number. Making the columns merely optional would also make several empty rows look like different bills, or collapse them into one row. | Keep the federal key for Congress rows and keep the Congress loader on it. Give a non-federal bill its own identity: session, originating organization where supplied, and official identifier. Do not parse `HB 264`. |
| `core.legislative_session` already uses an owned UUID and unique `(jurisdiction_id, identifier)`. | The provider uuid and the human session identifier are two values, and only `identifier` is stored. | Keep the UUID key. Let `identifier` hold the provider's jurisdiction-scoped session id. Add a nullable OCD/session id, unique when present, rather than promoting either value to the primary key. |
| `core.organization` has `jurisdiction_geoid` and no parent. It also has no artifact or payload column. | Hierarchy and place cannot be represented, and a new row would have nowhere to record evidence. | Add `parent_organization_id`. Add `jurisdiction_id` as a jurisdiction reference, separate from geography. Keep `organization_identifier`. Add nullable evidence columns; existing rows may stay without them, and a new promoted row must supply artifact or payload. |
| `core.bill_sponsorship.member_namespace` defaults to `bioguide`. `member_external_id` is required. `role` allows only sponsor or cosponsor. There is no primary-sponsor column. | A state sponsor is not a BioGuide id. A name-only sponsor cannot be stored honestly, and a default would label it as federal. | Writers must set the namespace; drop the BioGuide default. Keep `member_external_id` required so a name-only sponsor cannot enter this table. Add a nullable primary flag. Leave other role words in source detail. |
| `core.document` is uniquely `(document_type, source_key)` and carries GovInfo `congress`, `bill_type`, `bill_number`, and `version_code`. `core.bill_text_source_record` requires all of those federal keys. | An OpenStates document id is not a GovInfo package, and a state bill version cannot satisfy Congress, type, and number. | Keep owned `document_id`. Add `core.document_identifier`. Leave the federal columns nullable and unused for state rows. Distinguish a bill version from a supporting document with `document_type`. Keep `bill_text_source_record` as the GovInfo grain. A state version's lossless payload stays on the artifact/payload, linked by `document_id`, not in the GovInfo version table. |
| `core.roll_call.external_id` is `NOT NULL` and unique with jurisdiction and session. House and Senate loaders reload on that key. `roll_number` is the chamber number. | One column cannot name both a Senate vote number and an OCD vote id. | Add `core.roll_call_identifier` and copy today's federal `external_id` into it. Leave the current key in place until the loader is updated in the same change. Never copy an OCD vote id into `roll_number`. |
| `fact.member_vote` primary key is `(roll_call_id, person_id)`. | An unresolved voter has no person id. | Leave this key. Do not add a null person. Unresolved voters remain in the roll-call source record and in the reconciliation counts. `name_at_vote` is display text from a resolved federal file, not a join key. |

Partial dates stay out of `date` and `timestamp` columns. A year or a month remains source text. Membership still waits on person, organization, and optional post bridges. A post's source division id is not automatically `core.division.division_id`. Parent-derived coverage in `parent-derived-coverage.json` measured links; a missing link is "not supplied," not a publisher zero.

## Proposed schema diff (not implemented)

This replaces the earlier sketch that only made `bill_type` and `bill_number` optional. That sketch is withdrawn. Optional federal columns are not a civic model, and they would break the reload rules the Congress and chamber loaders already use.

No migration is written here. Nothing is copied from database `openstates`. Existing Congress, GovInfo, House, and Senate rows keep their values. A later story may change a loader only in the same change that changes the key that loader names, and a reload of a known Congress bill or roll call must return the same owned id.

The shared pattern is the one `core.person_identifier`, `core.bill_identifier`, and `core.organization_identifier` already use: our id on the entity, and each provider id in its own namespace.

**Bills.** Add `official_identifier`, `organization_id`, and `classification`. A Congress row still requires `bill_type` and `bill_number`. A state or local row requires `official_identifier` and `legislative_session_id`, and leaves the federal type and number empty. Those are two complete identities, not one identity with holes. `HB 264` is `official_identifier`. The OCD bill id stays in `core.bill_identifier`. The Congress reload in `sql/query/legislation/upsert_bill.sql` stays on `(jurisdiction, legislative_session, bill_type, bill_number)` for federal rows. Changing that unique index to a partial index requires that file to name the same partial key in the same change. A state session must not be stored in `legislative_session` as a Congress number, or the Congress fingerprint queries would mix the two.

**Sessions.** Add a nullable provider session id, unique when present. Do not replace `legislative_session_id`.

**Organizations.** Add `parent_organization_id` and `jurisdiction_id`. Do not put an OCD id in `jurisdiction_geoid`. Add evidence columns. Rows that already exist may lack evidence; a newly promoted row must have an artifact or a payload.

**Sponsorship.** The writer already supplies `member_namespace`, so the `bioguide` default can be removed without a new federal value. Add `is_primary`. A sponsor with no stable id stays out of this table.

**Documents.** Add `core.document_identifier (document_id, namespace, external_id)` with the same evidence rule as `core.bill_identifier`. Keep `congress`, `bill_type`, `bill_number`, and `version_code` as federal metadata. Keep `core.bill_text_source_record` as the GovInfo version grain. A state bill version is a `core.document` of its own type plus an identifier row, not a row in that GovInfo table.

**Roll calls.** Add `core.roll_call_identifier` and copy each current `external_id` into it under a House or Senate namespace. Leave `external_id` required, and leave `sql/query/votes/upsert_house_roll_call.sql` and `upsert_senate_roll_call.sql` on `(jurisdiction, legislative_session, external_id)`, until a later step edits those statements together with the key. An OpenStates vote id goes only in the identifier table. `roll_number` stays the federal roll number.

**Member votes.** No column change. An unresolved voter stays in the source record and in the reconciliation count.

Promotion of OpenStates rows is a story after this design is accepted and after issue #100 is actually complete.
