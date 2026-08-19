# Model

## Contract

Open Civic Data (OCD), as implemented by OpenStates, is the shared legislative
interoperability contract. The canonical warehouse represents these entities:

```
jurisdiction -> session -> organization -> person/membership
                             -> bill -> action/document/sponsorship/voteevent
                                                          -> personvote
```

Source identifiers remain first-class. OCD IDs, Bioguide IDs, GovInfo package
IDs, Congress numbers, bill type/number, and source URLs are never replaced by
an internal surrogate alone.

## Boundaries

| Database | Role | Write rule |
|---|---|---|
| `openstates` | Faithful OpenStates provider snapshot | Restore/refresh only; no warehouse changes |
| `opendiscourse` | Canonical research database | Adapters write normalized OCD-aligned tables and provenance |

The OpenStates dump includes an upstream Django application schema. We do not
write federal data directly into its `public.opencivicdata_*` tables: doing so
would make provider upgrades and provenance ambiguous. Instead, the canonical
database has OCD-aligned tables plus explicit source mappings. Views or FDW
queries expose the provider snapshot when needed.

## Federal mapping

| Federal source | Canonical OCD-aligned target |
|---|---|
| Congress.gov member + Congress Legislators | person, person_identifier, membership |
| GovInfo BILLSTATUS | bill, bill_action, bill_sponsorship, bill_subject, bill_document |
| GovInfo BILLS / BILLSUM | document, bill_document, document_chunk |
| House/Senate roll calls | voteevent, personvote |

The join key for federal people is Bioguide ID. The bill identity is Congress,
type, and number, with source-specific package/version IDs retained beside it.

## BILLSTATUS reconciliation mapping

The first federal loader reconciles GovInfo `BILLSTATUS` XML to the existing
Congress.gov bill grain. It never matches on a title or a person's display
name. The required source-to-model mapping is:

| BILLSTATUS XML field | Canonical target | Deterministic key / rule |
|---|---|---|
| `bill/congress`, `bill/type`, `bill/number` | `core.bill` | `us`, Congress number, lower-cased bill type, bill number |
| GovInfo XML member path | `core.bill_identifier` | namespace `govinfo.billstatus_xml`; one immutable source reference per bill |
| `actions/item` | `core.bill_action` | bill plus ordinal in the source XML; retain date, text, code, source system, and source reference |
| `sponsors/item/bioguideId` | `core.bill_sponsorship` → `core.person_identifier` | namespace `bioguide`; unresolved people remain explicit source identifiers, never name matches |
| `committees/item/systemCode` | `core.bill_committee` | namespace `congress.gov.committee`; preserve activity metadata |
| `subjects/*/item/name`, `policyArea/name` | `core.bill_subject` | namespace `congress.gov.subject`; preserve the original classification |
| `textVersions/item` | `core.bill_document` | text-version code plus official GovInfo URL; no text is fetched by BILLSTATUS ingestion |

Each normalized relationship must point to either the immutable source artifact
and its member path or an API raw payload. A loader may report an unresolved
foreign key, but it must not invent a person, committee, vote, or document
identity to make a join succeed.

## Rule

Before an adapter is added, write its source-to-model mapping and grain. Do not
invent a new entity when an OCD entity or source-mapping relation expresses it.
