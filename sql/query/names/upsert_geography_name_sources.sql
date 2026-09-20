-- One assertion per (geography, kind, dataset, vintage); same rerun rule as the person upsert.
-- %(rows)s is a JSON array of objects with the column names below.
INSERT INTO core.geography_name_source (
  geography_id, name_kind, name, dataset_id, source_vintage, artifact_id, payload_id, run_id
)
SELECT DISTINCT ON (geography_id, name_kind, dataset_id, source_vintage)
       geography_id, name_kind, name, dataset_id, source_vintage, artifact_id, payload_id, run_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(
  geography_id uuid, name_kind text, name text,
  dataset_id text, source_vintage text, artifact_id uuid, payload_id uuid, run_id uuid
)
ORDER BY geography_id, name_kind, dataset_id, source_vintage, name COLLATE "C"
ON CONFLICT (geography_id, name_kind, dataset_id, source_vintage) DO UPDATE
SET name = EXCLUDED.name,
    artifact_id = EXCLUDED.artifact_id,
    payload_id = EXCLUDED.payload_id,
    run_id = EXCLUDED.run_id,
    updated_at = now()
WHERE (core.geography_name_source.name, core.geography_name_source.artifact_id,
       core.geography_name_source.payload_id, core.geography_name_source.run_id)
  IS DISTINCT FROM (EXCLUDED.name, EXCLUDED.artifact_id, EXCLUDED.payload_id, EXCLUDED.run_id)
RETURNING (xmax = 0) AS inserted
