SELECT
    geography.geography_id,
    feature.layer,
    feature.name,
    feature.artifact_id
FROM stage.tiger_feature AS feature
JOIN core.geography AS geography
  ON geography.geography_type = CASE
        WHEN feature.layer IN ('zcta510', 'zcta520') THEN 'zcta'
        WHEN feature.layer = 'cd119' THEN 'congressional_district'
        ELSE feature.layer
     END
 AND geography.geoid = feature.geoid
WHERE feature.layer = ANY(%(layers)s)
  AND feature.artifact_id = ANY(%(artifact_ids)s)
  AND feature.name IS NOT NULL
  AND btrim(feature.name) <> ''
ORDER BY feature.layer, feature.geoid;
