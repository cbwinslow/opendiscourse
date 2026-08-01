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

## Rule

Before an adapter is added, write its source-to-model mapping and grain. Do not
invent a new entity when an OCD entity or source-mapping relation expresses it.
