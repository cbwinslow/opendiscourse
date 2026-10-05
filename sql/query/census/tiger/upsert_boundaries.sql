INSERT INTO core.geography_boundary
    (geography_id, boundary_vintage, valid_from, valid_to, geom, source_artifact_id)
SELECT
    geography.geography_id,
    %(vintage)s,
    %(valid_from)s::date,
    %(valid_to)s::date,
    feature.geom,
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
ON CONFLICT (geography_id, boundary_vintage) DO UPDATE
SET geom = EXCLUDED.geom,
    source_artifact_id = EXCLUDED.source_artifact_id,
    valid_from = COALESCE(EXCLUDED.valid_from, core.geography_boundary.valid_from),
    valid_to = COALESCE(EXCLUDED.valid_to, core.geography_boundary.valid_to)
RETURNING boundary_id;
