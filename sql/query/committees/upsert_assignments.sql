-- Replace the current member snapshot in place. An unknown BioGuide is kept
-- with an empty person link. A rerun of the same values changes nothing.
INSERT INTO core.committee_assignment (
  committee_id, person_id, bioguide, party, rank, title, stated_name, chamber,
  source_artifact_id, run_id
)
SELECT
  c.committee_id, p.person_id, r.bioguide, r.party, r.rank, r.title, r.stated_name, r.chamber,
  r.source_artifact_id, r.run_id
FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(
  thomas_key text, bioguide text, party text, rank integer, title text,
  stated_name text, chamber text, source_artifact_id uuid, run_id uuid
)
JOIN core.committee c ON c.thomas_key = r.thomas_key
LEFT JOIN core.person_identifier p
  ON p.namespace = 'bioguide' AND p.external_id = r.bioguide
ON CONFLICT (committee_id, bioguide) DO UPDATE
SET person_id = EXCLUDED.person_id,
    party = EXCLUDED.party,
    rank = EXCLUDED.rank,
    title = EXCLUDED.title,
    stated_name = EXCLUDED.stated_name,
    chamber = EXCLUDED.chamber,
    source_artifact_id = EXCLUDED.source_artifact_id,
    run_id = EXCLUDED.run_id,
    loaded_at = now()
WHERE (
  core.committee_assignment.person_id, core.committee_assignment.party, core.committee_assignment.rank,
  core.committee_assignment.title, core.committee_assignment.stated_name, core.committee_assignment.chamber,
  core.committee_assignment.source_artifact_id
) IS DISTINCT FROM (
  EXCLUDED.person_id, EXCLUDED.party, EXCLUDED.rank,
  EXCLUDED.title, EXCLUDED.stated_name, EXCLUDED.chamber,
  EXCLUDED.source_artifact_id
)
RETURNING (xmax = 0) AS inserted
