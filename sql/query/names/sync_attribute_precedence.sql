-- Upsert the file's ranking; only rows whose rank or field changed are touched. The rank
-- uniqueness is deferred, so a reordering inside one transaction never trips over itself.
INSERT INTO catalog.attribute_precedence (entity, name_kind, geography_type, dataset_id, rank, field)
SELECT entity, name_kind, geography_type, dataset_id, rank, field
FROM unnest(
  %(entities)s::text[], %(kinds)s::text[], %(types)s::text[],
  %(datasets)s::text[], %(ranks)s::smallint[], %(fields)s::text[]
) AS f(entity, name_kind, geography_type, dataset_id, rank, field)
ON CONFLICT (entity, name_kind, geography_type, dataset_id) DO UPDATE
SET rank = EXCLUDED.rank, field = EXCLUDED.field, updated_at = now()
WHERE (catalog.attribute_precedence.rank, catalog.attribute_precedence.field)
  IS DISTINCT FROM (EXCLUDED.rank, EXCLUDED.field)
RETURNING 1
