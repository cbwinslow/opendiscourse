# FEC coverage, grains, and completion contract

This companion makes “campaign-finance coverage from 2000–2024” testable. It does not authorize a bulk transfer; each batch still requires a fresh official manifest, capacity result, and operator approval.

## Target source families

The programme targets the FEC bulk products below whenever the FEC publishes an equivalent cycle file. The implementation must record the actual publisher availability by cycle; it must not invent a replacement product when a historical file is absent.

| Family | Research purpose | Initial typed grain | Important limit |
| --- | --- | --- | --- |
| Candidate master | Candidate identity, office, district, party, election metadata | candidate ID × source cycle | A candidate record is not by itself a person link. |
| Committee master | Committee identity, type, designation, party, treasurer/contact metadata | committee ID × source cycle | A committee is not necessarily a candidate committee. |
| Candidate–committee linkage | Official relationship between candidate and committee | candidate ID × committee ID × election/linkage version | Linkage must preserve its FEC election-year and linkage identifiers. |
| Itemized individual contributions (`indiv`) | Reported itemized receipt activity | cycle × family × FEC source record/submission ID | It is not all contributions or all donors; unitemized money is reported elsewhere. |
| Committee/candidate transactions (`pas2`) | Committee, PAC, party, and candidate contribution/independent-expenditure activity | cycle × family × FEC source record/submission ID | Preserve transaction classification and candidate/committee references. |
| Other transactions (`oth`) | Other reported committee transaction activity | cycle × family × FEC source record/submission ID | Do not fold it into individual contributions. |
| Operating expenditures (`oppexp`) | Reported committee operating expenditures | cycle × family × FEC source record/submission ID | Retain reporting/amendment identifiers and the source's stated fields. |
| Candidate/committee summaries and totals | Reported unitemized and aggregate context | reporting entity × cycle/reporting period × source record | Never substitute summary totals for itemized rows, or vice versa. |

If the FEC exposes another public bulk family that materially changes campaign-finance interpretation, the field inventory must classify it as in scope, deferred, or excluded with a reason before researchers are told coverage is complete.

## Required field treatment

Every source column and public nested field receives a versioned inventory row with: `family`, `cycle`, `source_member`, `source_path`, `source_type`, `disposition`, `typed_target`, `transformation`, `null_rate`, `source_key`, `amendment_role`, `reason`, and `mapping_version`.

| Disposition | Rule |
| --- | --- |
| `typed_fact` | Use a typed field/relation needed for filtering, joining, amount/date analysis, official keying, reporting lineage, or documented research metric. |
| `retained_source_detail` | Preserve it in source-shaped stage/source-record evidence when it has source value but is not a stable shared attribute. |
| `excluded` | Require a specific documented reason: duplicate evidence, confirmed implementation-only value, or non-public/unsafe material. Missing a mapping is never an exclusion. |

Money amounts, dates, transaction/report types, amendment indicators, report/file/submission IDs, entity identifiers, state/district/election fields, memo indicators/text, and source record identifiers are presumed `typed_fact` unless the review records a reason otherwise. A new or unknown field stops promotion review.

## Identity contract

```text
FEC candidate ID ── reviewed bridge ── BioGuide identifier ── core.person
        │
        └── FEC-native candidate/committee/fact rows remain useful even when unresolved
```

The bridge is one-way evidence, not a fuzzy matching service. An FEC candidate ID may be stored as an external identifier assertion. It creates a politician link only when the configured `person_join` gate is enabled and the bridge evidence is reviewed. Committee and donor names cannot bypass this rule.

## Batch completion checklist

A FEC family/cycle batch is complete only when:

1. The original FEC URL, published availability, byte size, checksum, artifact version, and run are retained.
2. The field inventory covers every field in the selected source member and the mapping has no unreviewed fields.
3. Typed facts have a documented immutable business key and partition/reload boundary; source-shaped records remain replayable.
4. Source selected/accepted/rejected/deferred/promoted rows and money totals reconcile to official published counts/totals where the publisher supplies a comparable measure. A non-comparable source must say why.
5. A rerun produces no duplicate facts, and an interrupted run can resume or fails with an explicit recovery command without deleting raw evidence.
6. The coverage report labels source family, cycles, itemized versus summary/unitemized scope, known gaps, and amendment/version rule.
7. Every person-keyed output either uses an approved identifier bridge or is reported as unresolved; tests prove a same-name record remains unlinked.
8. Required automated checks pass: fast checks for parser/manifest/idempotency rules, database checks for schema/promotion/reconciliation, and a bounded real-source proof only after transfer approval.

## Programme gates

1. **Pilot gate:** prove official manifest → capacity → approval → immutable evidence → stage → repeatability using the 2024 four-file selection.
2. **Model gate:** approve compact typed schema, source-field inventory, amendment/version treatment, and representative-cycle benchmark before historical transactions.
3. **History gate:** load masters and linkage, then approve transaction batches in bounded cycle/family groups with reconciliation and restart proof.
4. **Identity gate:** review bridge coverage and exceptions, then separately enable FEC-to-politician joins.
5. **Research gate:** publish documented marts only after their underlying coverage and identity dependencies are complete.
