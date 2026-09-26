-- Extra name facts. run_id changes only when the words or the file change, so a rerun is quiet.
INSERT INTO core.person_name_source (
  person_id, name_kind, full_name, given_name, family_name,
  dataset_id, source_vintage, artifact_id, payload_id, run_id
)
SELECT
  pi.person_id, s.name_kind, s.full_name, s.given_name, s.family_name,
  'congress.legislators', s.source_vintage, s.artifact_id, NULL, s.run_id
FROM profile_name AS s
JOIN core.person_identifier AS pi
  ON pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
ON CONFLICT (person_id, name_kind, dataset_id, source_vintage) DO UPDATE
SET full_name = EXCLUDED.full_name,
    given_name = EXCLUDED.given_name,
    family_name = EXCLUDED.family_name,
    artifact_id = EXCLUDED.artifact_id,
    payload_id = EXCLUDED.payload_id,
    run_id = EXCLUDED.run_id,
    updated_at = now()
WHERE (
  core.person_name_source.full_name,
  core.person_name_source.given_name,
  core.person_name_source.family_name,
  core.person_name_source.artifact_id
) IS DISTINCT FROM (
  EXCLUDED.full_name, EXCLUDED.given_name, EXCLUDED.family_name, EXCLUDED.artifact_id
)
RETURNING (xmax = 0) AS inserted
