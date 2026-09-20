-- Remove ranking rows the file no longer lists.
DELETE FROM catalog.attribute_precedence p
WHERE NOT EXISTS (
  SELECT 1
  FROM unnest(%(entities)s::text[], %(kinds)s::text[], %(types)s::text[], %(datasets)s::text[])
       AS f(entity, name_kind, geography_type, dataset_id)
  WHERE f.entity = p.entity AND f.name_kind = p.name_kind
    AND f.geography_type = p.geography_type AND f.dataset_id = p.dataset_id
)
RETURNING 1
