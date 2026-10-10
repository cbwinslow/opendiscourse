-- Link political divisions to the boundary of the matching vintage by identifier only:
-- state FIPS (from the OCD state code) plus the district code equals the TIGER GEOID.
-- U.S. House: 119th Congress. State legislatures: 2024 plan. No name comparison anywhere.
WITH state_map AS (
    SELECT postal, fips
    FROM unnest(%(postals)s::text[], %(fips)s::text[]) AS mapping(postal, fips)
), candidate AS (
    SELECT division.division_id,
           'congressional_district' AS geography_type,
           mapping.fips || CASE WHEN match[2] = 'at-large' THEN '00' ELSE lpad(match[2], 2, '0') END AS geoid,
           'legal_boundary' AS relationship_kind
    FROM core.division AS division
    CROSS JOIN LATERAL regexp_match(
        division.ocd_division_id, '^ocd-division/country:us/state:([a-z]{2})/cd:([0-9]+|at-large)$') AS match
    JOIN state_map AS mapping ON mapping.postal = match[1]
    WHERE division.ocd_division_id IS NOT NULL
  UNION ALL
    -- A delegate or commissioner represents the whole district or territory, whose
    -- congressional-district GEOID ends in 98.
    SELECT division.division_id, 'congressional_district', mapping.fips || '98', 'delegate_district'
    FROM core.division AS division
    CROSS JOIN LATERAL regexp_match(
        division.ocd_division_id, '^ocd-division/country:us/(?:district|territory):([a-z]{2})$') AS match
    JOIN state_map AS mapping ON mapping.postal = match[1]
    WHERE division.ocd_division_id IS NOT NULL
  UNION ALL
    SELECT division.division_id,
           match[2],
           mapping.fips || lpad(match[3], 3, '0'),
           'legal_boundary'
    FROM core.division AS division
    CROSS JOIN LATERAL regexp_match(
        division.ocd_division_id, '^ocd-division/country:us/state:([a-z]{2})/(sldu|sldl):([0-9]+)$') AS match
    JOIN state_map AS mapping ON mapping.postal = match[1]
    WHERE division.ocd_division_id IS NOT NULL
)
INSERT INTO core.division_boundary
    (division_id, boundary_id, valid_from, valid_to, congress, legislative_year,
     relationship_kind, source_artifact_id, metadata)
SELECT candidate.division_id,
       boundary.boundary_id,
       CASE WHEN candidate.geography_type = 'congressional_district' THEN %(cd_valid_from)s::date END,
       CASE WHEN candidate.geography_type = 'congressional_district' THEN %(cd_valid_to)s::date END,
       CASE WHEN candidate.geography_type = 'congressional_district' THEN %(congress)s::integer END,
       CASE WHEN candidate.geography_type <> 'congressional_district' THEN %(legislative_year)s::integer END,
       candidate.relationship_kind,
       boundary.source_artifact_id,
       jsonb_build_object('rule', 'state_fips_plus_district_code', 'geoid', candidate.geoid,
                          'geography_type', candidate.geography_type)
FROM candidate
JOIN core.geography AS geography
  ON geography.geography_type = candidate.geography_type AND geography.geoid = candidate.geoid
JOIN core.geography_boundary AS boundary
  ON boundary.geography_id = geography.geography_id AND boundary.boundary_vintage = %(vintage)s
ON CONFLICT (division_id, boundary_id) DO NOTHING
RETURNING division_boundary_id;
