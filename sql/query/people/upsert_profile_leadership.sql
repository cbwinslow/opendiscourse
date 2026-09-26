INSERT INTO core.person_leadership (
  person_id, bioguide, chamber, title, start_date, end_date, source_artifact_id, run_id
)
SELECT pi.person_id, s.bioguide, s.chamber, s.title, s.start_date, s.end_date, s.artifact_id, s.run_id
FROM profile_leadership AS s
LEFT JOIN core.person_identifier AS pi
  ON pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
ON CONFLICT (bioguide, chamber, title, start_date) DO UPDATE
SET person_id = EXCLUDED.person_id,
    end_date = EXCLUDED.end_date,
    source_artifact_id = EXCLUDED.source_artifact_id,
    run_id = EXCLUDED.run_id,
    loaded_at = now()
WHERE (
  core.person_leadership.person_id,
  core.person_leadership.end_date,
  core.person_leadership.source_artifact_id
) IS DISTINCT FROM (
  EXCLUDED.person_id, EXCLUDED.end_date, EXCLUDED.source_artifact_id
)
RETURNING (xmax = 0) AS inserted
