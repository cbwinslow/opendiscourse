-- Seed one OCD division per numeric-coded state legislative district found in the loaded
-- TIGER SLD boundaries. The OCD id is built from the official state postal code, chamber
-- and district code, never from a display name. A district code is a number, or for the states
-- whose official codes are letter-suffixed (Alaska senate A-T, Maryland, Minnesota, North Dakota
-- and South Dakota house seats such as 01A) the same code as OCD writes it: leading zeros dropped,
-- lower case ('01A' -> '1a', '00A' -> 'a'). Rows that already exist are left alone.
WITH state_map AS (
    SELECT postal, fips
    FROM unnest(%(postals)s::text[], %(fips)s::text[]) AS mapping(postal, fips)
), sld AS (
    SELECT geography.geography_type AS chamber,
           geography.geoid,
           geography.name,
           mapping.postal,
           CASE WHEN substr(geography.geoid, 3) ~ '^[0-9]{3}$' THEN substr(geography.geoid, 3)::int::text
                WHEN mapping.postal IN ('ak', 'md', 'mn', 'nd', 'sd')
                 AND substr(geography.geoid, 3) ~ '^[0-9]{2}[A-Z]$'
                THEN lower(ltrim(substr(geography.geoid, 3), '0'))
           END AS code,
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
      AND (geography.geography_type || ':' || geography.geoid) <> ALL(%(skip_keys)s::text[])
)
INSERT INTO core.division (ocd_division_id, label, classification, source_artifact_id, metadata)
SELECT format('ocd-division/country:us/state:%%s/%%s:%%s', postal, chamber, code),
       concat_ws(' ', coalesce(state_name, upper(postal)), name),
       chamber,
       source_artifact_id,
       jsonb_build_object('seeded_from', 'census.tiger', 'geoid', geoid, 'legislative_year', %(vintage)s)
FROM sld
WHERE code IS NOT NULL
ON CONFLICT (ocd_division_id) WHERE ocd_division_id IS NOT NULL DO NOTHING
RETURNING division_id;
