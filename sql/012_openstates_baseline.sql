-- Open Civic Data-compatible legislative dimensions owned by OpenDiscourse.
-- These tables are not a copy of the upstream OpenStates Django schema.

CREATE TABLE IF NOT EXISTS core.jurisdiction (
  jurisdiction_id text PRIMARY KEY,
  name text NOT NULL,
  classification text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS core.legislative_session (
  legislative_session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  jurisdiction_id text NOT NULL REFERENCES core.jurisdiction(jurisdiction_id),
  identifier text NOT NULL,
  name text,
  classification text,
  starts_on date,
  ends_on date,
  active boolean,
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (jurisdiction_id, identifier),
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
);

ALTER TABLE core.bill
  ADD COLUMN IF NOT EXISTS legislative_session_id uuid REFERENCES core.legislative_session(legislative_session_id),
  ADD COLUMN IF NOT EXISTS ocd_id text;
CREATE UNIQUE INDEX IF NOT EXISTS bill_ocd_id_idx ON core.bill (ocd_id) WHERE ocd_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS core.membership (
  membership_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_id uuid NOT NULL REFERENCES core.person(person_id),
  organization_id uuid NOT NULL REFERENCES core.organization(organization_id),
  legislative_session_id uuid REFERENCES core.legislative_session(legislative_session_id),
  role text NOT NULL,
  start_date date,
  end_date date,
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS membership_person_idx ON core.membership(person_id);
CREATE INDEX IF NOT EXISTS membership_organization_idx ON core.membership(organization_id);

ALTER TABLE core.roll_call
  ADD COLUMN IF NOT EXISTS bill_id uuid REFERENCES core.bill(bill_id),
  ADD COLUMN IF NOT EXISTS legislative_session_id uuid REFERENCES core.legislative_session(legislative_session_id),
  ADD COLUMN IF NOT EXISTS organization_id uuid REFERENCES core.organization(organization_id),
  ADD COLUMN IF NOT EXISTS ocd_id text;
CREATE UNIQUE INDEX IF NOT EXISTS roll_call_ocd_id_idx ON core.roll_call (ocd_id) WHERE ocd_id IS NOT NULL;
