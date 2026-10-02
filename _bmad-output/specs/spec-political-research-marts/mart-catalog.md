# Political mart catalog and release criteria

## Catalog

| Mart | One row represents | Required dependencies | Release condition |
| --- | --- | --- | --- |
| `politician_profile` | one resolved `core.person` | person identifiers/names; office-term history | No finance or FEC fields unless the FEC identity bridge is enabled; unresolved source identities are counted separately. |
| `office_term` | one person holding one post/role for one dated term | jurisdiction, organization, post, membership, source evidence | Role, party, organization, division, and dates retain source provenance; overlapping terms are shown rather than arbitrarily merged. |
| `member_vote` | one person’s recorded position on one vote event | roll call, member vote, person identifier, session/organization | Vote option/raw text, timing, source, and any unresolved voter state remain visible. |
| `bill_analysis` | one canonical bill identity | bill, action, sponsorship, subject, document, session | Status/action dates and classifications retain source vocabulary; document/version analysis is a distinct relation or future mart, never an alternate row grain. |
| `candidate_cycle_finance` | one FEC candidate ID × cycle | approved FEC candidate master/linkage/facts; reviewed person bridge if person-keyed | Measures are columns with family/cycle coverage; candidate-to-committee linkage is explicit and itemized, summary/unitemized, transfer, and expenditure measures remain separate. |
| `committee_cycle_finance` | one FEC committee ID × cycle | approved FEC committee master/linkage/facts | Measures are columns with family/cycle coverage; a committee is not treated as a person and no person bridge is implied. |
| `district_year` | one political/geographic division for one defined period and boundary vintage | approved geography, boundary/crosswalk, measurements, office-term linkage when needed | It is not published across redistricting until comparable-vintage rules are documented. |

## Required shared fields

Every released mart includes its stable key(s), `coverage_status`, `coverage_note`, `source_dataset_ids`, `source_artifact_ids` or an evidence drill-through key, `as_of`/source-vintage field, and documentation of its time period. A person-keyed mart additionally states the identity namespace(s) used and records whether the relation is `verified`, `unresolved`, or `not_applicable`.

`coverage_status` has these permitted values:

| Value | Meaning |
| --- | --- |
| `complete_for_declared_scope` | All listed dependency checks passed for the stated population/time range. |
| `partial` | Some documented rows, periods, jurisdictions, or source families are absent. |
| `unavailable` | The source did not publish an equivalent record or the requested period is outside declared coverage. |
| `unresolved_identity` | The underlying record exists but cannot safely connect to a person. |
| `not_comparable` | A geographic/time relationship needed for the requested comparison has not been approved. |

## Derived metrics

Marts may calculate transparent measures—such as vote participation, bills introduced, total itemized amount, or number of committees—only when the formula, denominator, source families, coverage, and date range are published with the model. A metric is not a judgment of a politician.

## Definition of done

A mart is ready only when:

1. Its declared grain has a uniqueness test and a documented stable key.
2. Its dependencies have passed their own source completion contracts for the declared scope.
3. dbt schema tests cover non-null keys, relationships, allowed coverage states, and duplicate prevention.
4. Semantic tests prove time, identity, and geographic-vintage safeguards.
5. A researcher-facing description gives sample-safe joins, formulas, source citations, coverage, and known limitations.
6. Evidence drill-through resolves to the retained artifact/payload/run without exposing raw staging as the product interface.
7. A refresh changes only rows supported by changed canonical facts; the run records the model version and source-vintage range.
