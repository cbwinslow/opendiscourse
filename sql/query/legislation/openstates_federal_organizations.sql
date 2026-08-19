SELECT id AS ocd_id, name, classification, parent_id, extras
FROM openstates_source.opencivicdata_organization
WHERE jurisdiction_id = 'ocd-jurisdiction/country:us/government'
ORDER BY id;
