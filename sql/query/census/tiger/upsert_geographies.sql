WITH source_rows AS (
    SELECT DISTINCT
        CASE
            WHEN layer IN ('zcta510', 'zcta520') THEN 'zcta'
            WHEN layer = 'cd119' THEN 'congressional_district'
            ELSE layer
        END AS geography_type,
        geoid,
        state_fips,
        county_fips
    FROM stage.tiger_feature
    WHERE layer = ANY(%(layers)s)
      AND artifact_id = ANY(%(artifact_ids)s)
)
INSERT INTO core.geography
    (geography_type, geoid, state_fips, county_fips)
SELECT geography_type, geoid, state_fips, county_fips
FROM source_rows
ON CONFLICT (geography_type, geoid) DO UPDATE
SET state_fips = EXCLUDED.state_fips,
    county_fips = EXCLUDED.county_fips
RETURNING geography_id;
