INSERT INTO core.district_office (
  person_id, bioguide, office_key, address, building, suite, city, state, zip,
  phone, fax, hours, latitude, longitude, location, source_artifact_id, run_id
)
SELECT
  pi.person_id, s.bioguide, s.office_key, s.address, s.building, s.suite, s.city, s.state, s.zip,
  s.phone, s.fax, s.hours, s.latitude, s.longitude,
  CASE
    WHEN s.latitude IS NULL THEN NULL
    ELSE ST_SetSRID(ST_MakePoint(s.longitude, s.latitude), 4326)
  END,
  s.artifact_id, s.run_id
FROM profile_office AS s
LEFT JOIN core.person_identifier AS pi
  ON pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
ON CONFLICT (office_key) DO UPDATE
SET person_id = EXCLUDED.person_id,
    bioguide = EXCLUDED.bioguide,
    address = EXCLUDED.address,
    building = EXCLUDED.building,
    suite = EXCLUDED.suite,
    city = EXCLUDED.city,
    state = EXCLUDED.state,
    zip = EXCLUDED.zip,
    phone = EXCLUDED.phone,
    fax = EXCLUDED.fax,
    hours = EXCLUDED.hours,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    location = EXCLUDED.location,
    source_artifact_id = EXCLUDED.source_artifact_id,
    run_id = EXCLUDED.run_id,
    loaded_at = now()
WHERE (
  core.district_office.person_id, core.district_office.bioguide, core.district_office.address,
  core.district_office.building, core.district_office.suite, core.district_office.city,
  core.district_office.state, core.district_office.zip, core.district_office.phone,
  core.district_office.fax, core.district_office.hours, core.district_office.latitude,
  core.district_office.longitude, core.district_office.source_artifact_id
) IS DISTINCT FROM (
  EXCLUDED.person_id, EXCLUDED.bioguide, EXCLUDED.address, EXCLUDED.building, EXCLUDED.suite,
  EXCLUDED.city, EXCLUDED.state, EXCLUDED.zip, EXCLUDED.phone, EXCLUDED.fax, EXCLUDED.hours,
  EXCLUDED.latitude, EXCLUDED.longitude, EXCLUDED.source_artifact_id
)
RETURNING (xmax = 0) AS inserted
