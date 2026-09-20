-- One assertion per (person, kind, dataset, vintage). A rerun with the same evidence changes
-- nothing; a corrected value or evidence from a newer run updates the row in place.
-- %(rows)s is a JSON array of objects with the column names below.
INSERT INTO core.person_name_source (
  person_id, name_kind, full_name, given_name, family_name,
  dataset_id, source_vintage, artifact_id, payload_id, run_id
)
SELECT DISTINCT ON (person_id, name_kind, dataset_id, source_vintage)
       person_id, name_kind, full_name, given_name, family_name,
       dataset_id, source_vintage, artifact_id, payload_id, run_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(
  person_id uuid, name_kind text, full_name text, given_name text, family_name text,
  dataset_id text, source_vintage text, artifact_id uuid, payload_id uuid, run_id uuid
)
ORDER BY person_id, name_kind, dataset_id, source_vintage, full_name COLLATE "C"
ON CONFLICT (person_id, name_kind, dataset_id, source_vintage) DO UPDATE
SET full_name = EXCLUDED.full_name,
    given_name = EXCLUDED.given_name,
    family_name = EXCLUDED.family_name,
    artifact_id = EXCLUDED.artifact_id,
    payload_id = EXCLUDED.payload_id,
    run_id = EXCLUDED.run_id,
    updated_at = now()
WHERE (core.person_name_source.full_name, core.person_name_source.given_name, core.person_name_source.family_name,
       core.person_name_source.artifact_id, core.person_name_source.payload_id, core.person_name_source.run_id)
  IS DISTINCT FROM
      (EXCLUDED.full_name, EXCLUDED.given_name, EXCLUDED.family_name,
       EXCLUDED.artifact_id, EXCLUDED.payload_id, EXCLUDED.run_id)
RETURNING (xmax = 0) AS inserted
