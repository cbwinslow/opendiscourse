SELECT v.id AS ocd_id, v.identifier, v.start_date, v.organization_id, v.bill_id,
       v.motion_text, v.result
FROM openstates_source.opencivicdata_voteevent v
JOIN openstates_source.opencivicdata_legislativesession s ON s.id = v.legislative_session_id
WHERE s.identifier = %(congress)s
ORDER BY v.id
LIMIT %(limit)s;
