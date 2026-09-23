-- One whole file row (a committee body, or one member) per identity.
INSERT INTO core.committee_source_record (
  source_file, thomas_key, bioguide, record, source_artifact_id, run_id
)
SELECT source_file, thomas_key, bioguide, record, source_artifact_id, run_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(
  source_file text, thomas_key text, bioguide text, record jsonb,
  source_artifact_id uuid, run_id uuid
)
ON CONFLICT (source_file, thomas_key, bioguide) DO UPDATE
SET record = EXCLUDED.record,
    source_artifact_id = EXCLUDED.source_artifact_id,
    run_id = EXCLUDED.run_id,
    loaded_at = now()
WHERE (
  core.committee_source_record.record, core.committee_source_record.source_artifact_id
) IS DISTINCT FROM (
  EXCLUDED.record, EXCLUDED.source_artifact_id
)
RETURNING (xmax = 0) AS inserted
