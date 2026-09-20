-- Remove display rows the file no longer lists.
DELETE FROM catalog.name_display d
WHERE NOT EXISTS (
  SELECT 1
  FROM unnest(%(entities)s::text[], %(kinds)s::text[]) AS f(entity, name_kind)
  WHERE f.entity = d.entity AND f.name_kind = d.name_kind
)
RETURNING 1
