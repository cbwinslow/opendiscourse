-- Retire divisions this pipeline seeded from a Census number where the reviewed crosswalk gives the
-- real Open Civic Data id (Massachusetts and New Hampshire House, DC wards, Puerto Rico). A seeded
-- division is derived, carries no seat and no post; its links go with it. Anything that has a post, or
-- was not seeded from Census, is never touched.
WITH retired AS (
    SELECT division.division_id
    FROM core.division AS division
    WHERE division.metadata->>'seeded_from' = 'census.tiger'
      AND (division.classification || ':' || (division.metadata->>'geoid')) = ANY(%(keys)s::text[])
      AND division.ocd_division_id <> ALL(%(ocd_ids)s::text[])
      AND NOT EXISTS (SELECT 1 FROM core.post WHERE post.division_id = division.division_id)
), links AS (
    DELETE FROM core.division_boundary AS link USING retired
    WHERE link.division_id = retired.division_id
    RETURNING link.division_id
)
DELETE FROM core.division AS division USING retired
WHERE division.division_id = retired.division_id
RETURNING division.ocd_division_id;
