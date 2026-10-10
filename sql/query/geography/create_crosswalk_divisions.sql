-- Create the division a reviewed crosswalk pair names when OpenStates promotion has not already
-- created it (a division created in the same statement would be invisible to the link step).
WITH pair AS (
    SELECT * FROM unnest(%(geoids)s::text[], %(chambers)s::text[], %(ocd_ids)s::text[], %(names)s::text[])
        AS mapping(geoid, chamber, ocd_division_id, census_name)
), target AS (
    SELECT pair.*, boundary.boundary_id, boundary.source_artifact_id
    FROM pair
    JOIN core.geography AS geography
      ON geography.geography_type = pair.chamber AND geography.geoid = pair.geoid
    JOIN core.geography_boundary AS boundary
      ON boundary.geography_id = geography.geography_id AND boundary.boundary_vintage = %(vintage)s
)
INSERT INTO core.division (ocd_division_id, label, classification, source_artifact_id, metadata)
SELECT target.ocd_division_id, target.census_name, target.chamber, target.source_artifact_id,
       jsonb_build_object('seeded_from', 'ocd_sld_crosswalk', 'geoid', target.geoid,
                          'legislative_year', %(vintage)s)
FROM target
ON CONFLICT (ocd_division_id) WHERE ocd_division_id IS NOT NULL DO NOTHING
RETURNING division_id;
