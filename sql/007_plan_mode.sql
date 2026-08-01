ALTER TABLE ingest.run DROP CONSTRAINT IF EXISTS run_mode_check;
ALTER TABLE ingest.run
  ADD CONSTRAINT run_mode_check
  CHECK (mode IN ('backfill', 'incremental', 'manual', 'plan'));
