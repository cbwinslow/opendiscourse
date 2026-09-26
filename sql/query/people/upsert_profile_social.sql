INSERT INTO core.person_social_account (
  person_id, bioguide, network, handle, external_id, source_artifact_id, run_id
)
SELECT pi.person_id, s.bioguide, s.network, s.handle, s.external_id, s.artifact_id, s.run_id
FROM profile_social AS s
LEFT JOIN core.person_identifier AS pi
  ON pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
ON CONFLICT (bioguide, network) DO UPDATE
SET person_id = EXCLUDED.person_id,
    handle = EXCLUDED.handle,
    external_id = EXCLUDED.external_id,
    source_artifact_id = EXCLUDED.source_artifact_id,
    run_id = EXCLUDED.run_id,
    loaded_at = now()
WHERE (
  core.person_social_account.person_id,
  core.person_social_account.handle,
  core.person_social_account.external_id,
  core.person_social_account.source_artifact_id
) IS DISTINCT FROM (
  EXCLUDED.person_id, EXCLUDED.handle, EXCLUDED.external_id, EXCLUDED.source_artifact_id
)
RETURNING (xmax = 0) AS inserted
