-- Add identifiers the database does not have yet. An identifier that already
-- exists is never moved or rewritten, whichever person owns it.
WITH resolved AS (
  SELECT s.*, COALESCE(b.person_id, s.new_person_id) AS person_id
  FROM legislator_stage s
  LEFT JOIN core.person_identifier b
    ON b.namespace = 'bioguide' AND b.external_id = s.bioguide
)
INSERT INTO core.person_identifier (person_id, namespace, external_id, source_artifact_id, source_run_id)
SELECT person_id, namespace, external_id, artifact_id, run_id FROM resolved
ON CONFLICT (namespace, external_id) DO NOTHING
