-- Name removed terms on the run in the transaction that removes them: after it commits, the
-- warehouse holds them nowhere else, and a rerun would find nothing to report.
UPDATE ingest.run
SET parameters = parameters || jsonb_build_object('superseded_terms', %(terms)s::jsonb)
WHERE run_id = %(run_id)s
