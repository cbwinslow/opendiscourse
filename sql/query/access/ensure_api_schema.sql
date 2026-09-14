-- Empty PostgREST surface. Reviewed read-only views belong here later.
-- Never expose ingest, stage, or raw payloads through this schema.
CREATE SCHEMA IF NOT EXISTS api;

COMMENT ON SCHEMA api IS
  'Read-only PostgREST/research HTTP surface. Views are reviewed; core/ingest stay private.';
