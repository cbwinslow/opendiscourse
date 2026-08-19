DELETE FROM catalog.resource
WHERE dataset_id = %(dataset_id)s
  AND resource_key LIKE %(prefix)s
