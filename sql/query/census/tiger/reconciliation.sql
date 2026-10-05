WITH staged AS (
    SELECT layer, count(*)::bigint AS staged_rows
    FROM stage.tiger_feature
    WHERE layer = ANY(%(layers)s)
      AND artifact_id = ANY(%(artifact_ids)s)
    GROUP BY layer
),
loaded AS (
    SELECT feature.layer, count(DISTINCT boundary.boundary_id)::bigint AS loaded_boundaries
    FROM stage.tiger_feature AS feature
    JOIN core.geography AS geography
      ON geography.geography_type = CASE
            WHEN feature.layer IN ('zcta510', 'zcta520') THEN 'zcta'
            WHEN feature.layer = 'cd119' THEN 'congressional_district'
            ELSE feature.layer
         END
     AND geography.geoid = feature.geoid
    JOIN core.geography_boundary AS boundary
      ON boundary.geography_id = geography.geography_id
     AND boundary.boundary_vintage = %(vintage)s
     AND boundary.source_artifact_id = feature.artifact_id
    WHERE feature.layer = ANY(%(layers)s)
      AND feature.artifact_id = ANY(%(artifact_ids)s)
    GROUP BY feature.layer
)
SELECT
    staged.layer,
    staged.staged_rows,
    COALESCE(loaded.loaded_boundaries, 0)::bigint AS loaded_boundaries
FROM staged
LEFT JOIN loaded USING (layer)
ORDER BY staged.layer;
