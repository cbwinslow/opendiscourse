-- Terms that would collide with one the survivor already has (membership_term_key).
SELECT count(*) AS collisions
FROM core.membership d
JOIN core.membership s
  ON s.person_id = %(survivor)s AND s.organization_id = d.organization_id
 AND s.role = d.role AND s.start_date = d.start_date
 AND s.source_artifact_id IS NOT NULL AND d.source_artifact_id IS NOT NULL
WHERE d.person_id = %(duplicate)s
