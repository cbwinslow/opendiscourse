-- Stable project-owned read views over the OpenStates snapshot and canonical data.
-- The FDW is environment-specific, so this migration is intentionally a no-op
-- until the approved openstates_source foreign schema has been provisioned.

CREATE SCHEMA IF NOT EXISTS leg;

DO $$
BEGIN
  IF to_regclass('openstates_source.opencivicdata_person') IS NULL THEN
    RAISE NOTICE 'OpenStates FDW is not provisioned; skipping leg.person view';
  ELSE
    EXECUTE $view$
      CREATE OR REPLACE VIEW leg.person AS
      SELECT
        person.id AS entity_id,
        person.id AS ocd_id,
        'openstates'::text AS source_system,
        person.name,
        person.given_name,
        person.family_name,
        person.current_jurisdiction_id,
        person.extras AS metadata
      FROM openstates_source.opencivicdata_person AS person
      UNION ALL
      SELECT
        person.person_id::text AS entity_id,
        identifier.external_id AS ocd_id,
        'opendiscourse'::text AS source_system,
        person.full_name AS name,
        person.given_name,
        person.family_name,
        NULL::text AS current_jurisdiction_id,
        person.metadata
      FROM core.person AS person
      LEFT JOIN LATERAL (
        SELECT external_id
        FROM core.person_identifier
        WHERE person_id = person.person_id
          AND namespace = 'ocd'
        ORDER BY valid_from NULLS LAST
        LIMIT 1
      ) AS identifier ON TRUE
    $view$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('openstates_source.opencivicdata_bill') IS NULL THEN
    RAISE NOTICE 'OpenStates FDW is not provisioned; skipping leg.bill view';
  ELSE
    EXECUTE $view$
      CREATE OR REPLACE VIEW leg.bill AS
      SELECT
        bill.id AS entity_id,
        bill.id AS ocd_id,
        'openstates'::text AS source_system,
        jurisdiction.id AS jurisdiction_id,
        session.identifier AS legislative_session_identifier,
        bill.identifier,
        bill.title,
        bill.classification,
        bill.subject,
        bill.first_action_date,
        bill.latest_action_date,
        bill.latest_action_description,
        bill.extras AS metadata
      FROM openstates_source.opencivicdata_bill AS bill
      JOIN openstates_source.opencivicdata_legislativesession AS session
        ON session.id = bill.legislative_session_id
      JOIN openstates_source.opencivicdata_jurisdiction AS jurisdiction
        ON jurisdiction.id = session.jurisdiction_id
      UNION ALL
      SELECT
        bill.bill_id::text AS entity_id,
        bill.ocd_id,
        'opendiscourse'::text AS source_system,
        COALESCE(session.jurisdiction_id, bill.jurisdiction) AS jurisdiction_id,
        COALESCE(session.identifier, bill.legislative_session) AS legislative_session_identifier,
        bill.bill_type || ' ' || bill.bill_number AS identifier,
        bill.title,
        ARRAY[bill.bill_type]::text[] AS classification,
        ARRAY[]::text[] AS subject,
        bill.introduced_date::text AS first_action_date,
        bill.latest_action_date::text AS latest_action_date,
        bill.latest_action AS latest_action_description,
        bill.metadata
      FROM core.bill AS bill
      LEFT JOIN core.legislative_session AS session
        ON session.legislative_session_id = bill.legislative_session_id
    $view$;
  END IF;
END $$;
