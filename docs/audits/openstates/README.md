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
baseline. A restart uses a new directory and repeats measurements; it cannot
reuse incomplete evidence until both restored-artifact lineage and the full
snapshot fingerprint have been independently established. This conservative
restart currently favors correctness over avoiding repeated scans.
Raw checkpoints remain on the operator's disk and are ignored by Git; versioned
assembled inventories, matrices, reports and supplementary evidence carry the
reviewable result. No checkpoint or retained source artifact is deleted.

`audit.json` contains every discovered relation and scalar field, exhaustive
public JSON/array paths, catalog-declared keys, counts/null rates/date bounds,
FDW exposure and actual reader probes, observed jurisdiction/session groups,
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
