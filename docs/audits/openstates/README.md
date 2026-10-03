# Read-only snapshot audit

Run the standalone audit with explicitly supplied connections. Put any credentials
in environment variables outside this repository; the command receives only their
names. Choose a new output directory for every run. Each SQL measurement runs in
an isolated read-only transaction with statement and lock timeouts.

```sh
uv run python -m opendiscourse_research.openstatesaudit \
  --source-dsn-env OPENDISCOURSE_AUDIT_SOURCE \
  --warehouse-dsn-env OPENDISCOURSE_AUDIT_WAREHOUSE \
  --output docs/audits/openstates/NEW-RUN --timeout-ms 60000
```

`checkpoint-*.json` files retain completed catalog, relation and reference phases
even if the process stops. They are incomplete evidence, never an approved
baseline. `--resume-from` may reuse a relation or reference measurement only
when that checkpoint says reuse is allowed, its nested paths are tagged, its
coverage rows name a method, and its catalog baseline matches the new catalog
exactly. A different baseline is rejected and measured again. Failed scopes stay
visible and are not reused. An exported database snapshot expires when the
connection that created it closes, so resume never reattaches one. Pass a new
`--output` directory; resume reads the old directory and does not rewrite it.
Raw checkpoints remain on the operator's disk and are ignored by Git; versioned
assembled inventories, matrices, reports and supplementary evidence carry the
reviewable result. No checkpoint or retained source artifact is deleted.

`audit.json` contains every discovered relation and scalar field, exhaustive
public JSON/array paths, catalog-declared keys, counts/null rates/date bounds,
FDW exposure and actual reader probes, observed jurisdiction/session groups
(including groups reached through declared parent links, with broken links kept
visible),
identifier and BioGuide measurements, reference reconciliation, current owned
columns and proposed mapping targets. Restricted application/account relations
are catalog-only. No private row values or connection secrets are emitted.

Exit code 2 means the audit produced incomplete evidence. Query failures retain
their exact scope and SQLSTATE; unavailable counts remain null, never invented
zeros. FDW absence is `present_but_unreadable`, never implicit exclusion. Public
nested paths come from exhaustive scans; timeout is an explicit coverage gap.
Unknown relation classifications block completion.

Proposed field targets are reviewed against current owned columns; matching
names alone do not approve semantic compatibility. Every other public field is
retained verbatim with its source key. Typed targets, schema deltas and the
mapping version require independent review before promotion. New event,
document/version, office and other targets belong to the later schema story;
existing posts and memberships are not proposed as new copied source tables.

The fingerprint records candidate usable artifacts from `ingest.current_artifact`,
but deliberately does not assert which archive was restored. A matching registered
checksum is not restore proof. No restore attestation was discovered during the
initial operator-approved audit. This gap blocks a verified baseline and Story 1
completion. No baseline approval, schema edit, FDW expansion, promotion, FEC
transfer or person join is performed by this command.

Future promotion starts with a separately approved bounded pilot, preserving
immutable artifact/payload/run lineage per row. It must reconcile source counts
and stable keys against accepted/rejected/deferred/promoted counts, all foreign
references against resolved/unresolved targets, every approved field against its
retained source evidence, and every output row against immutable provenance.
Reruns must reconcile the same source-key grain without duplicate promotion.
Display names never connect providers; OpenStates/OCD assertions stay namespaced,
federal identity requires BioGuide, and FEC links remain separately gated.
