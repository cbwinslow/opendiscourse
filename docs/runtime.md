# Runtime

## Primary database

Use the bare-metal PostgreSQL 17 cluster on port `5434`. Its `odspace`
tablespace is located at:

```
/home/cbwinslow/workspace/data-lake/opendiscourse/pg17
```

It contains two intentionally separate databases:

| Database | Role |
|---|---|
| `opendiscourse` | Canonical catalog, raw lineage, curated entities, facts, documents, and vectors |
| `openstates` | Provider staging database restored from the OpenStates dump; never alter its source schema to fit the warehouse |

The local `cbwinslow` PostgreSQL role uses peer authentication. The application
DSN is `postgresql:///opendiscourse?port=5434`; it avoids credentials in the
repository and must remain local-only unless a separate service role/TLS plan
is created.

The role also has a password set, used only by the `dbt/` mart-layer project
over TCP loopback (`127.0.0.1:5434`) — its Postgres adapter cannot use a Unix
socket. This does not change the primary peer-auth path above; see
`docs/mart.md` for why and how it's kept out of the repository.

## OpenStates

The OpenStates source schema is a provider implementation schema (including
Django tables), not the OpenDiscourse schema. Keep it isolated. Extract or
foreign-query only the Open Civic Data tables needed for canonical mappings;
preserve provider IDs such as OCD IDs and Bioguide identifiers.

The restore uses PostgreSQL 17 tools and PostGIS 3. A split schema/data dump
must load the data serially with foreign-key triggers disabled during restore;
parallel data restore can violate dependency order.

`opendiscourse` accesses the approved OpenStates relations through the
read-only `openstates_source` foreign schema. This is an integration boundary,
not a write target; see `docs/openstates-integration.md` for the privilege and
deployment policy.

## Docker

`compose.yaml` is an optional development fallback on port `5433`. It is not
the production data store. Do not run migrations against it by accident: set a
Docker-specific `DATABASE_URL` explicitly before using Compose.
