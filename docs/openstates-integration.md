# OpenStates integration

## Decision

The `openstates` PostgreSQL database is a read-only, versioned provider
snapshot. It contains the upstream Django and Open Civic Data tables such as
`opencivicdata_bill`, `opencivicdata_person`, and `opencivicdata_voteevent`.
Do not insert OpenDiscourse, Congress.gov, GovInfo, or local reconciliation
rows into that database.

`opendiscourse` is the owned canonical warehouse. It adopts the Open Civic Data
entity semantics and IDs where applicable, but retains raw-source lineage and
source-native identifiers required for reproducible federal ingestion.

## Ownership and identifier policy

| Concern | OpenStates snapshot | OpenDiscourse canonical layer |
|---|---|---|
| Owner | Upstream provider restore | This project |
| Writes | Restore/refresh only | Ordered migrations and reviewed loaders |
| State/local entities | Original OCD rows and IDs | Read-only mapped or deliberately promoted copies |
| Federal entities | Never write | Congress.gov, GovInfo, House, and Senate records |
| Person join | OCD ID / provider identifier | Bioguide ID as the federal deterministic key |
| Bill join | OCD bill ID | Congress + type + number, with source identifiers retained |
| Provenance | Provider URLs/metadata | Raw payload/artifact, checksum, member path, parser version, and run |

Compatibility views must label the source and never hide unresolved mappings.
They are for query interoperability; the canonical source tables remain the
place for writes, quality checks, and embeddings.

## Canonical compatibility map

OpenDiscourse does not duplicate the upstream Django implementation, but its
owned tables use the same entity grains and preserve an OCD ID when one is
published or deterministically assigned by an approved mapping rule.

| OpenStates source relation | Owned canonical relation | Federal source and deterministic identifier |
|---|---|---|
| `opencivicdata_jurisdiction` | `core.jurisdiction` | United States: `ocd-jurisdiction/country:us/government` |
| `opencivicdata_legislativesession` | `core.legislative_session` | Congress number under the U.S. jurisdiction |
| `opencivicdata_organization` | `core.organization` | Chamber/committee source code or published OCD ID |
| `opencivicdata_person` + `personidentifier` | `core.person` + `person_identifier` | Bioguide ID; never a display-name match |
| `opencivicdata_membership` semantics | `core.membership` | Bioguide ID + chamber/office + bounded term evidence |
| `opencivicdata_bill` + `billidentifier` | `core.bill` + `bill_identifier` | Congress + lower-cased type + number |
| `opencivicdata_billaction` | `core.bill_action` | Bill key + source XML/API ordinal |
| `opencivicdata_billsponsorship` | `core.bill_sponsorship` | Bill key + Bioguide ID + sponsorship role |
| `opencivicdata_billdocument` | `core.bill_document` | Bill key + version code + official URL |
| `opencivicdata_voteevent` + `personvote` | `core.roll_call` + `fact.member_vote` | Official chamber roll-call ID + Bioguide ID |

The `core` schema is deliberately a canonical compatibility layer, not an ORM
database. Its tables add raw artifact/payload references, source member paths,
checksums, and reconciliation metadata that the upstream provider snapshot
does not own.

## Least-privilege FDW setup

An administrator must create the FDW path because the application role should
not have permission to create database roles, alter authentication, or own a
cross-database superuser mapping. Use a dedicated login constrained to
`SELECT` on an allow-list of public OpenStates tables.

For a networked or managed deployment, run the following as a PostgreSQL
administrator after selecting and storing a secret for `openstates_fdw` outside
this repository:

```sql
CREATE ROLE openstates_fdw LOGIN PASSWORD '<managed-secret>' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
GRANT CONNECT ON DATABASE openstates TO openstates_fdw;
\c openstates
GRANT USAGE ON SCHEMA public TO openstates_fdw;
GRANT SELECT ON TABLE
  public.opencivicdata_jurisdiction,
  public.opencivicdata_legislativesession,
  public.opencivicdata_organization,
  public.opencivicdata_person,
  public.opencivicdata_personidentifier,
  public.opencivicdata_bill,
  public.opencivicdata_billaction,
  public.opencivicdata_billsponsorship,
  public.opencivicdata_billdocument,
  public.opencivicdata_voteevent,
  public.opencivicdata_personvote
TO openstates_fdw;
```

Then, as an administrator of `opendiscourse`, install `postgres_fdw`, create a
server pointing at the local `openstates` database, and create a user mapping
for the OpenDiscourse application role. Keep the password in the database's
protected user mapping, not in `.env`, source control, output, or a migration.
Import only the approved tables into an `openstates_source` schema. After
verification, create project-owned compatibility views in a dedicated schema;
do not expose raw foreign tables as the stable application interface.

### Local peer-authenticated deployment

The current workstation uses a Unix-domain socket and PostgreSQL peer
authentication. Its administrator has provisioned the same `openstates_fdw`
role without a password, with an FDW server owned by `postgres` and a mapping
that explicitly starts each remote session as `openstates_fdw`. PostgreSQL
requires the administrator-owned mapping to set `password_required=false` for
this local-only peer path; application roles have only `USAGE` on the server
and `SELECT` on the imported `openstates_source` foreign tables. Do not copy
this mode to a TCP, shared-host, or hosted-database deployment.

## Promotion workflow

1. Record the source snapshot/version and verify row counts and identifiers.
2. Map an entity grain and deterministic identifiers before writing a loader.
3. Read via the FDW; do not write across it.
4. Ingest federal sources into immutable raw lineage, then project into owned
   OCD-aligned tables with explicit source mappings.
5. Reconcile by stable identifiers only. Leave ambiguous people, bills, and
   votes unresolved and visible in a quality report.
6. Publish compatibility views only after duplicate, null-key, coverage, and
   referential-integrity checks pass.
