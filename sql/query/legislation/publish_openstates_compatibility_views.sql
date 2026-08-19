-- Project-owned views published only after an approved OpenStates FDW remap.
CREATE SCHEMA IF NOT EXISTS leg;

CREATE OR REPLACE VIEW leg.person AS
SELECT
  person.id AS entity_id, person.id AS ocd_id, 'openstates'::text AS source_system,
  person.name, person.given_name, person.family_name, person.current_jurisdiction_id,
  person.extras AS metadata
FROM openstates_source.opencivicdata_person AS person
UNION ALL
SELECT
  person.person_id::text, identifier.external_id, 'opendiscourse'::text,
  person.full_name, person.given_name, person.family_name, NULL::text, person.metadata
FROM core.person AS person
LEFT JOIN LATERAL (
  SELECT external_id FROM core.person_identifier
  WHERE person_id = person.person_id AND namespace = 'ocd'
  ORDER BY valid_from NULLS LAST LIMIT 1
) AS identifier ON TRUE;

CREATE OR REPLACE VIEW leg.bill AS
SELECT
  bill.id AS entity_id, bill.id AS ocd_id, 'openstates'::text AS source_system,
  jurisdiction.id AS jurisdiction_id, session.identifier AS legislative_session_identifier,
  bill.identifier, bill.title, bill.classification, bill.subject, bill.first_action_date,
  bill.latest_action_date, bill.latest_action_description, bill.extras AS metadata
FROM openstates_source.opencivicdata_bill AS bill
JOIN openstates_source.opencivicdata_legislativesession AS session
  ON session.id = bill.legislative_session_id
JOIN openstates_source.opencivicdata_jurisdiction AS jurisdiction
  ON jurisdiction.id = session.jurisdiction_id
UNION ALL
SELECT
  bill.bill_id::text, bill.ocd_id, 'opendiscourse'::text,
  COALESCE(session.jurisdiction_id, bill.jurisdiction),
  COALESCE(session.identifier, bill.legislative_session),
  bill.bill_type || ' ' || bill.bill_number, bill.title,
  ARRAY[bill.bill_type]::text[], ARRAY[]::text[], bill.introduced_date::text,
  bill.latest_action_date::text, bill.latest_action, bill.metadata
FROM core.bill AS bill
LEFT JOIN core.legislative_session AS session
  ON session.legislative_session_id = bill.legislative_session_id;
