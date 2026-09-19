-- A person is new only when no person already owns this BioGuide id.
-- Never matched on name or any other attribute (ADR-0002 decision 2).
INSERT INTO core.person (person_id, full_name, given_name, family_name, metadata)
SELECT DISTINCT ON (s.bioguide)
  s.new_person_id, s.full_name, s.given_name, s.family_name,
  jsonb_build_object('canonical_baseline', 'congress-legislators')
FROM legislator_stage s
WHERE NOT EXISTS (
  SELECT 1 FROM core.person_identifier i
  WHERE i.namespace = 'bioguide' AND i.external_id = s.bioguide
)
ORDER BY s.bioguide
