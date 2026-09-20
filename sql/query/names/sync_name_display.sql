-- Upsert the file's display order; only rows whose position changed are touched.
INSERT INTO catalog.name_display (entity, name_kind, position)
SELECT entity, name_kind, position
FROM unnest(%(entities)s::text[], %(kinds)s::text[], %(positions)s::smallint[]) AS f(entity, name_kind, position)
ON CONFLICT (entity, name_kind) DO UPDATE
SET position = EXCLUDED.position, updated_at = now()
WHERE catalog.name_display.position IS DISTINCT FROM EXCLUDED.position
RETURNING 1
