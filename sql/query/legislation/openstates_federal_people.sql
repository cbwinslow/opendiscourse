SELECT id AS ocd_id, name, given_name, family_name, extras
FROM openstates_source.opencivicdata_person
WHERE current_jurisdiction_id = 'ocd-jurisdiction/country:us/government'
ORDER BY id;
