-- A person is new only when no person owns any identifier the source asserts for this
-- BioGuide id (legislator_group). Never matched on name or any other attribute (ADR-0002).
INSERT INTO core.person (person_id, full_name, given_name, family_name, metadata)
SELECT DISTINCT ON (s.bioguide)
  s.new_person_id, s.full_name, s.given_name, s.family_name,
  jsonb_build_object('canonical_baseline', 'congress-legislators')
FROM legislator_stage s
JOIN legislator_group g ON g.bioguide = s.bioguide AND g.outcome = 'new'
ORDER BY s.bioguide
