-- Add identifiers the database does not have yet, to the one person the group resolved
-- to. An identifier that already exists is never moved or rewritten; a group with a
-- conflict writes nothing.
INSERT INTO core.person_identifier (person_id, namespace, external_id, source_artifact_id, source_run_id)
SELECT g.person_id, s.namespace, s.external_id, s.artifact_id, s.run_id
FROM legislator_stage s
JOIN legislator_group g ON g.bioguide = s.bioguide AND g.outcome IN ('new', 'matched')
ON CONFLICT (namespace, external_id) DO NOTHING
