SELECT scheme AS namespace, identifier AS external_id
FROM openstates_source.opencivicdata_personidentifier
WHERE person_id = %(ocd_id)s
ORDER BY scheme, identifier;
