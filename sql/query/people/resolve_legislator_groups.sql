-- One row per BioGuide id in the staged file: which existing person(s) already own
-- any identifier the source asserts for it (ADR-0005, Decision 1). Never by name.
--   new                nobody owns any of them: a person is created
--   matched            exactly one person owns some of them: the rest are attached to it
--   multiple_owners    two or more persons own them: nothing is written, a conflict is recorded
--   bioguide_mismatch  the single owner already has a different BioGuide id, or another
--                      staged BioGuide resolves to the same owner: one person, two BioGuide ids
CREATE TEMP TABLE legislator_group ON COMMIT DROP AS
WITH wanted AS (
  SELECT DISTINCT ON (bioguide) bioguide, new_person_id FROM legislator_stage ORDER BY bioguide
), owners AS (
  -- Two equi-joins (index lookups), not one join on an OR.
  SELECT s.bioguide, i.person_id
  FROM legislator_stage s
  JOIN core.person_identifier i ON i.namespace = s.namespace AND i.external_id = s.external_id
  UNION
  SELECT s.bioguide, i.person_id
  FROM (SELECT DISTINCT bioguide FROM legislator_stage) s
  JOIN core.person_identifier i ON i.namespace = 'bioguide' AND i.external_id = s.bioguide
), summary AS (
  SELECT w.bioguide, w.new_person_id,
         coalesce(array_agg(o.person_id ORDER BY o.person_id) FILTER (WHERE o.person_id IS NOT NULL), '{}') AS owner_ids
  FROM wanted w
  LEFT JOIN owners o USING (bioguide)
  GROUP BY w.bioguide, w.new_person_id
), shared AS (
  SELECT owner_ids[1] AS owner_id
  FROM summary
  WHERE cardinality(owner_ids) = 1
  GROUP BY owner_ids[1]
  HAVING count(*) > 1
)
SELECT sm.bioguide, sm.new_person_id, sm.owner_ids,
       CASE
         WHEN cardinality(sm.owner_ids) = 0 THEN 'new'
         WHEN cardinality(sm.owner_ids) > 1 THEN 'multiple_owners'
         WHEN sm.owner_ids[1] IN (SELECT owner_id FROM shared) THEN 'bioguide_mismatch'
         WHEN EXISTS (
           SELECT 1 FROM core.person_identifier b
           WHERE b.person_id = sm.owner_ids[1] AND b.namespace = 'bioguide' AND b.external_id <> sm.bioguide
         ) THEN 'bioguide_mismatch'
         ELSE 'matched'
       END AS outcome,
       coalesce(sm.owner_ids[1], sm.new_person_id) AS person_id
FROM summary sm
