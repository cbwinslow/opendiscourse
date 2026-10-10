-- Create the minimum identity row (type and GEOID only) for each overlapping geography a
-- relationship file names. Names and shapes belong to TIGER and are never written here.
INSERT INTO core.geography (geography_type, geoid, state_fips, county_fips)
SELECT DISTINCT
       %(geography_type)s,
       staged.overlap_geoid,
       CASE WHEN %(state_prefix)s::boolean THEN substr(staged.overlap_geoid, 1, 2) END,
       CASE WHEN %(county_prefix)s::boolean THEN substr(staged.overlap_geoid, 3, 3) END
FROM stage.census_relationship_row AS staged
WHERE staged.artifact_id = %(artifact_id)s
  AND staged.district_geoid IS NOT NULL
  AND staged.overlap_geoid IS NOT NULL
ON CONFLICT (geography_type, geoid) DO NOTHING
RETURNING geography_id;
