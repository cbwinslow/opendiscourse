INSERT INTO catalog.discovery (discovery_id, dataset_id, state, cursor, statistics, started_at)
VALUES (%(discovery_id)s, %(dataset_id)s, 'running', '{}'::jsonb, '{}'::jsonb, now())
ON CONFLICT (discovery_id) DO UPDATE SET
  state = 'running',
  error_message = NULL,
  started_at = COALESCE(catalog.discovery.started_at, now()),
  updated_at = now()
WHERE catalog.discovery.state <> 'running'
   OR catalog.discovery.updated_at < now() - interval '15 minutes'
RETURNING discovery_id, dataset_id, state, cursor, statistics;
