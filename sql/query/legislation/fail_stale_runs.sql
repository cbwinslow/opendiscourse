UPDATE ingest.run
SET status = 'failed',
    finished_at = now(),
    error_message = 'Recovered by congressional health check: run exceeded the stale-run threshold without completion.'
WHERE status = 'running'
  AND started_at < now() - %(older_than)s::interval
  AND dataset_id IN ('congress.govinfo_billstatus', 'openstates.legislation')
RETURNING run_id, dataset_id, started_at;
