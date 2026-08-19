SELECT resource_id
FROM catalog.resource
WHERE dataset_id = %(dataset)s
  AND (%(year)s::integer IS NULL OR release_year = %(year)s)
  AND (%(product)s::text IS NULL OR resource_type = %(product)s)
ORDER BY resource_key;
