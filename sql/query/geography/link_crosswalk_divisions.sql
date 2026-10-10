-- Link Census districts to divisions through the reviewed crosswalk (identifier pairs only):
-- ``inventory/geography/ocd-sld-crosswalk-2024.csv``.
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
INSERT INTO core.division_boundary
    (division_id, boundary_id, legislative_year, relationship_kind, source_artifact_id, metadata)
SELECT division.division_id, target.boundary_id, %(legislative_year)s::integer, 'legal_boundary',
       target.source_artifact_id,
       jsonb_build_object('rule', 'reviewed_ocd_crosswalk', 'geoid', target.geoid,
                          'geography_type', target.chamber)
FROM target
JOIN core.division AS division ON division.ocd_division_id = target.ocd_division_id
ON CONFLICT (division_id, boundary_id) DO NOTHING
RETURNING division_boundary_id;
