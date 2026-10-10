-- Block-assignment district codes that reached no TIGER district of the plan, by code.
SELECT staged.district_code, substr(staged.block_geoid, 1, 2) AS state_fips, count(*) AS blocks
FROM stage.census_block_assignment AS staged
LEFT JOIN core.geography AS district
  ON district.geography_type = %(district_type)s
 AND district.geoid = substr(staged.block_geoid, 1, 2) || staged.district_code
WHERE staged.artifact_id = %(artifact_id)s AND district.geography_id IS NULL
GROUP BY 1, 2
ORDER BY 3 DESC, 1, 2;
