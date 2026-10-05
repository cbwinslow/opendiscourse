WITH staged AS (
    SELECT
        count(*)::bigint AS staged_rows,
        count(DISTINCT geoid)::bigint AS staged_geoids
    FROM stage.tiger_feature
    WHERE artifact_id = %(artifact_id)s
      AND layer = %(layer)s
),
published AS (
    SELECT
        count(DISTINCT boundary.boundary_id)::bigint AS loaded_boundaries,
        count(*) FILTER (
            WHERE boundary.valid_from IS DISTINCT FROM %(valid_from)s::date
        )::bigint AS valid_from_mismatches,
        count(*) FILTER (
            WHERE boundary.valid_to IS DISTINCT FROM %(valid_to)s::date
        )::bigint AS valid_to_mismatches
    FROM stage.tiger_feature AS feature
    JOIN core.geography AS geography
      ON geography.geography_type = %(geography_type)s
     AND geography.geoid = feature.geoid
    JOIN core.geography_boundary AS boundary
      ON boundary.geography_id = geography.geography_id
     AND boundary.boundary_vintage = %(vintage)s
     AND boundary.source_artifact_id = feature.artifact_id
    WHERE feature.artifact_id = %(artifact_id)s
      AND feature.layer = %(layer)s
)
SELECT
    staged.staged_rows,
    staged.staged_geoids,
    published.loaded_boundaries,
    published.valid_from_mismatches,
    published.valid_to_mismatches
FROM staged
CROSS JOIN published;
