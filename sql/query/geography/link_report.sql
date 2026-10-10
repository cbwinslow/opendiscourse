-- Reconcile what linked against what exists, per boundary family. A district whose GEOID ends
-- in ZZ means "no districts defined" in TIGER; it is counted apart, not as a failure.
SELECT geography.geography_type,
       count(*) AS boundaries,
       count(*) FILTER (WHERE link.boundary_id IS NOT NULL) AS linked,
       count(*) FILTER (WHERE link.boundary_id IS NULL AND geography.geoid ~ 'Z+$') AS placeholder_unlinked,
       count(*) FILTER (WHERE link.boundary_id IS NULL AND geography.geoid !~ 'Z+$') AS unlinked
FROM core.geography AS geography
JOIN core.geography_boundary AS boundary
  ON boundary.geography_id = geography.geography_id AND boundary.boundary_vintage = %(vintage)s
LEFT JOIN (SELECT DISTINCT boundary_id FROM core.division_boundary) AS link
  ON link.boundary_id = boundary.boundary_id
WHERE geography.geography_type IN ('congressional_district', 'sldu', 'sldl')
GROUP BY geography.geography_type
ORDER BY geography.geography_type;
