-- Identity rows for 2020 census blocks (GEOID only; no polygon is downloaded or stored).
INSERT INTO core.geography (geography_type, geoid, parent_geoid, state_fips, county_fips)
SELECT DISTINCT 'block',
       staged.block_geoid,
       substr(staged.block_geoid, 1, 12),
       substr(staged.block_geoid, 1, 2),
       substr(staged.block_geoid, 3, 3)
FROM stage.census_block_assignment AS staged
WHERE staged.artifact_id = %(artifact_id)s
ON CONFLICT (geography_type, geoid) DO NOTHING
RETURNING geography_id;
