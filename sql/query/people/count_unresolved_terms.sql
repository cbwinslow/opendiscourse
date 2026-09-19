-- Staged terms whose BioGuide id is not in the warehouse (never matched any other way).
SELECT count(*) AS unresolved
FROM term_stage AS s
WHERE NOT EXISTS (
  SELECT 1 FROM core.person_identifier AS pi
  WHERE pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
)
