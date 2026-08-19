INSERT INTO catalog.discovery
  (discovery_id, dataset_id, state, cursor, statistics, error_message, started_at, finished_at)
VALUES
  (%(discovery_id)s, %(dataset_id)s, %(state)s, %(cursor)s, %(statistics)s,
   %(error_message)s, %(started_at)s, %(finished_at)s)
ON CONFLICT (discovery_id) DO UPDATE SET
  state = EXCLUDED.state,
  cursor = EXCLUDED.cursor,
  statistics = EXCLUDED.statistics,
  error_message = EXCLUDED.error_message,
  started_at = COALESCE(catalog.discovery.started_at, EXCLUDED.started_at),
  finished_at = EXCLUDED.finished_at,
  updated_at = now();
