# 2026-10-02 audit evidence

Update after the review corrections: `mapping-review.json` is a proposal, not an
approval. It applies the current field and constraint decisions to the live
catalog and does not remeasure null rates. `parent-derived-coverage.json` counts
child rows through declared parent links. It had no query failures. Jurisdiction
and legislative-session groups in that file come from a second read-only query
so each source key is its own group; the other tables share one earlier exported
snapshot. A null group or a relation with no path is not a publisher zero.
Neither file proves which archive bytes were restored. `run-02/` was not rewritten.

The current attempt is **run-02/**. It repeats bounded read-only measurements;
the earlier attempt was interrupted by an unsupported UUID serialization error
when saving public jurisdiction/session coverage. That defect has been fixed.

The checkpoint files directly in this directory are retained incomplete evidence
from that failed attempt. `checkpoint-0044-relation.json` is empty because the
old writer opened it before serialization failed. It is failed evidence, not a
successful measurement. Do not treat any earlier checkpoint as an approved
baseline or reuse it to bypass the current attempt. No retained files were removed.

`reference-and-administrative-counts.json` adds separately observed aggregate
counts for implementation/extension/reference relations without sampling private
values. Its geographic/legacy reference fields receive retained treatment; both
boundary relations and the legacy bill crosswalk have observed zero rows.
These additional observations are not a verified same-artifact baseline.

`safe-public-samples.json` provides one deterministic public source ID and safe
date/classification structure example for each of the 38 civic tables. It contains
no private account values or personal contact fields. The original run records
zero samples because this supplementary check was added after that run started.

Verification: the fast gate passed 670 tests before the later permission-recovery
test was added; the current targeted unit suite passes 17 tests. The full isolated
database gate passed 398 tests. The audit database suite additionally rechecked
the optimized exhaustive nested query and quoted-identifier/read-only guarantees.

The final fast gate passed 671 tests after all implementation changes. The
completed `run-02/audit.json` contains 129 relations: 84 tables, four extension
views and 41 sequences (database key allocators), with 761 scalar columns and
364 nested path/type entries before scoped retries. The run exits 2 as designed,
because incomplete evidence cannot pass approval gates.

Remaining acceptance gaps extend beyond artifact lineage and mapping approval.
Temporal bounds currently measure native date/timestamp fields only. Text-form
bill action, session and membership dates need separately validated treatment.
Coverage currently groups direct jurisdiction/session columns only; child
bill/event references still need derivation to report jurisdiction × entity ×
session/time range. Do not interpret the current coverage artifact as exhaustive
historical/geographic coverage. The original collection retains four query
timeouts; separate bounded retry artifacts resolve only the scopes they name.

Nested-field null-rate qualification: 356 of the original 364 entries lack
`null_rate_scope`; they inherited the source column's SQL-null rate. Their
exhaustive paths and occurrence counts are useful, but those inherited rates
must not be presented as per-path null/missingness measurements. The current
query computes an explicitly scoped rate over present path occurrences, with
absent paths distinguished from observed JSON nulls. The classification retry
uses that corrected query. The earlier path-rate measurements remain pending
completion; no broad rerun or silent evidence rewrite was performed.

The current **nested-field-disposition.json** resolves that rate qualification
offline: it derives exact present-path JSON-null rates from the original exhaustive
per-path/type occurrence counts and the successful classification retry, while
retaining source-column SQL-null rates separately. It contains 366 path/type
entries; the original run remains unchanged. A mixed-array null test verifies the
derivation. No broad source rescan was needed.

Final scoped retries: classification, billaction-to-bill and personvote-to-person
were measured successfully; both reference retries found zero unresolved targets.
Personvote-to-voteevent still timed out after 180 seconds, so that reconciliation
count remains unknown and is a completion blocker.

`organization-and-role-coverage.json` is a reproducible 30-second-bounded
aggregate using the maintained coverage query: the snapshot has 58 executive
organization rows and 1,798 government organization rows, plus 70 Governor and
1,631 Mayor membership rows. These are source row counts, not distinct people
or proof of complete nationwide governors/local-official coverage. No person
join was performed and publisher availability remains unknown.

Successful checkpoints contain catalog metadata, public field paths and aggregate
measurements only; private application/account row values are never sampled.
`run-02/audit.json`, once written, is the current complete collection of measured
results and scoped failures. An audit collection is not a completion claim:
missing restore lineage and independent mapping review block Story 1 closure.
