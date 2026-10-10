-- Whole-block tabulation assignment. The district GEOID is state FIPS (first two digits of the
-- block GEOID) plus the plan's district code. TIGER polygons remain the truth where a plan
-- splits a block.
INSERT INTO core.geography_crosswalk
    (from_geography_id, to_geography_id, from_vintage, to_vintage, method, weight_type, weight,
     quality_flag, source_dataset_id, source_artifact_id, source_ordinal)
SELECT block.geography_id,
       district.geography_id,
       %(from_vintage)s,
       %(to_vintage)s,
       'block_assignment',
       'assignment',
       1.0,
       'whole_block_tabulation',
       %(dataset_id)s,
       staged.artifact_id,
       staged.source_ordinal
FROM stage.census_block_assignment AS staged
JOIN core.geography AS block
  ON block.geography_type = 'block' AND block.geoid = staged.block_geoid
JOIN core.geography AS district
  ON district.geography_type = %(district_type)s
 AND district.geoid = substr(staged.block_geoid, 1, 2) || staged.district_code
WHERE staged.artifact_id = %(artifact_id)s
ON CONFLICT ON CONSTRAINT geography_crosswalk_source_key DO NOTHING
RETURNING geography_crosswalk_id;
