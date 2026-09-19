-- BioGuide ids the duplicate holds that the survivor does not: two people, not one.
SELECT count(*) AS collisions
FROM core.person_identifier d
WHERE d.person_id = %(duplicate)s AND d.namespace = 'bioguide'
  AND d.external_id NOT IN (
    SELECT external_id FROM core.person_identifier WHERE person_id = %(survivor)s AND namespace = 'bioguide'
  )
  AND EXISTS (SELECT 1 FROM core.person_identifier WHERE person_id = %(survivor)s AND namespace = 'bioguide')
