-- Catalog search support. These operations are idempotent because init-db
-- replays the legacy bootstrap SQL before applying Alembic revisions.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE INDEX IF NOT EXISTS resource_title_trgm_idx
  ON catalog.resource USING gin (title gin_trgm_ops);

CREATE INDEX IF NOT EXISTS resource_fts_idx
  ON catalog.resource USING gin (
    to_tsvector(
      'english',
      coalesce(resource_key, '') || ' ' || coalesce(title, '') || ' ' ||
      coalesce(summary, '') || ' ' || coalesce(universe, '') || ' ' ||
      coalesce(resource_type, '') || ' ' || coalesce(metadata::text, '')
    )
  );
