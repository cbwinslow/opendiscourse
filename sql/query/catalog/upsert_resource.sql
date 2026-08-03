INSERT INTO catalog.resource
    (dataset_id, resource_key, resource_type, title, summary, release_year, metadata)
VALUES
    (%(dataset_id)s, %(resource_key)s, %(resource_type)s, %(title)s,
     %(summary)s, %(release_year)s, %(metadata)s)
ON CONFLICT (dataset_id, resource_key) DO UPDATE SET
    resource_type = EXCLUDED.resource_type,
    title = EXCLUDED.title,
    summary = EXCLUDED.summary,
    release_year = EXCLUDED.release_year,
    metadata = EXCLUDED.metadata,
    updated_at = now()
