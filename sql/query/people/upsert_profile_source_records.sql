-- One safety copy per file entry. A rerun of the same bytes does not rewrite run_id.
INSERT INTO core.legislator_source_record (
  source_file, member_key, bioguide, record, source_artifact_id, run_id
)
SELECT source_file, member_key, bioguide, record, artifact_id, run_id
FROM profile_source
ON CONFLICT (source_file, member_key, bioguide) DO UPDATE
SET record = EXCLUDED.record,
    source_artifact_id = EXCLUDED.source_artifact_id,
    run_id = EXCLUDED.run_id,
    loaded_at = now()
WHERE (
  core.legislator_source_record.record,
  core.legislator_source_record.source_artifact_id
) IS DISTINCT FROM (EXCLUDED.record, EXCLUDED.source_artifact_id)
RETURNING (xmax = 0) AS inserted
