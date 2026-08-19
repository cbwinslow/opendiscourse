INSERT INTO catalog.resource (dataset_id, resource_key, resource_type, title, summary, metadata)
VALUES ('fred.series', %(key)s, 'series', %(title)s, %(summary)s, %(metadata)s)
ON CONFLICT (dataset_id, resource_key) DO UPDATE SET
  resource_type = EXCLUDED.resource_type,
  title = EXCLUDED.title,
  summary = EXCLUDED.summary,
  metadata = EXCLUDED.metadata,
  updated_at = now();
