-- Seed one OCD division per numeric-coded state legislative district found in the loaded
-- TIGER SLD boundaries. The OCD id is built from the official state postal code, chamber
-- and district number, never from a display name. Rows that already exist are left alone.
WITH state_map AS (
    SELECT postal, fips
    FROM unnest(%(postals)s::text[], %(fips)s::text[]) AS mapping(postal, fips)
), sld AS (
    SELECT geography.geography_type AS chamber,
           geography.geoid,
           geography.name,
           mapping.postal,
           state.name AS state_name,
           boundary.source_artifact_id
    FROM core.geography AS geography
    JOIN state_map AS mapping ON mapping.fips = substr(geography.geoid, 1, 2)
    JOIN core.geography_boundary AS boundary
      ON boundary.geography_id = geography.geography_id
     AND boundary.boundary_vintage = %(vintage)s
    LEFT JOIN core.geography AS state
      ON state.geography_type = 'state' AND state.geoid = substr(geography.geoid, 1, 2)
    WHERE geography.geography_type IN ('sldu', 'sldl')
      AND substr(geography.geoid, 3) ~ '^[0-9]{3}$'
)
INSERT INTO core.division (ocd_division_id, label, classification, source_artifact_id, metadata)
SELECT format('ocd-division/country:us/state:%%s/%%s:%%s', postal, chamber, substr(geoid, 3)::int),
       concat_ws(' ', coalesce(state_name, upper(postal)), name),
       chamber,
       source_artifact_id,
       jsonb_build_object('seeded_from', 'census.tiger', 'geoid', geoid, 'legislative_year', %(vintage)s)
FROM sld
ON CONFLICT (ocd_division_id) WHERE ocd_division_id IS NOT NULL DO NOTHING
RETURNING division_id;
