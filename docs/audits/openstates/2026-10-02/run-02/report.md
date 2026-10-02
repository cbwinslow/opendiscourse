# OpenStates snapshot evidence audit

Status: incomplete. Restore lineage and mapping approval remain unresolved.

Remaining coverage acceptance work: date bounds cover native date/timestamp
columns only; text-form bill action/session/membership dates need validated
treatment. Jurisdiction/session groups currently use direct fields only;
relationships through bills/events must be derived for full child-entity coverage.
The separate reference/count and sample artifacts correct or supplement the
original collection without rewriting it. Scoped retry artifacts resolve only
their named queries; they do not prove restore lineage or approve a baseline.
Earlier nested entries without `null_rate_scope` inherited their parent column's
null rate; these are not per-path null/missingness measurements. Their structural
paths/counts remain evidence, while path-rate completion remains pending.

Inventoried 129 relations (including sequences), 761 scalar columns and 364 nested path/type entries.
Proposed civic research relations: 38. FDW catalog relations: 11.

A missing FDW relation is present-but-unreadable, not excluded. Actual remote probes are recorded in relation-inventory.json.

Publisher historical availability cannot be inferred from this dump. Missing groups and query failures are unknown, not zero.

Proposed mapping targets require independent semantic/type review. No schema, reader, promotion or cross-provider identity writes occurred.

## Unresolved measurements

- public.opencivicdata_billaction.classification: exhaustive nested paths: unresolved (57014)
- opencivicdata_billac_bill_id_32c574af_fk_opencivic: unresolved (57014)
- opencivicdata_person_vote_event_id_7d507bb5_fk_opencivic: unresolved (57014)
- opencivicdata_person_voter_id_6740775f_fk_opencivic: unresolved (57014)

Next: review the relation/field matrices, establish restored-artifact lineage, resolve listed gaps, and approve the baseline before the separate schema/reader and bounded-pilot stories. Issue #100 remains open.
