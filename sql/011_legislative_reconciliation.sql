-- Reversible source-native relationships for federal legislative reconciliation.

CREATE TABLE IF NOT EXISTS core.bill_identifier (
  bill_id uuid NOT NULL REFERENCES core.bill(bill_id),
  namespace text NOT NULL,
  external_id text NOT NULL,
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  source_url text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (namespace, external_id),
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS bill_identifier_bill_idx ON core.bill_identifier(bill_id);

ALTER TABLE core.bill_action
  ADD COLUMN IF NOT EXISTS source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  ADD COLUMN IF NOT EXISTS source_member text,
  ADD COLUMN IF NOT EXISTS source_ordinal integer,
  ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE core.bill_action
  ALTER COLUMN source_payload_id DROP NOT NULL;
ALTER TABLE core.bill_action
  DROP CONSTRAINT IF EXISTS bill_action_source_evidence;
ALTER TABLE core.bill_action
  ADD CONSTRAINT bill_action_source_evidence
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS bill_action_source_member_idx
  ON core.bill_action (bill_id, source_artifact_id, source_member, source_ordinal)
  WHERE source_artifact_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS core.bill_sponsorship (
  bill_sponsorship_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id uuid NOT NULL REFERENCES core.bill(bill_id),
  person_id uuid REFERENCES core.person(person_id),
  member_namespace text NOT NULL DEFAULT 'bioguide',
  member_external_id text NOT NULL,
  role text NOT NULL CHECK (role IN ('sponsor', 'cosponsor')),
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  source_member text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE NULLS NOT DISTINCT (bill_id, member_namespace, member_external_id, role, source_artifact_id, source_member),
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS bill_sponsorship_person_idx ON core.bill_sponsorship(person_id);

CREATE TABLE IF NOT EXISTS core.bill_committee (
  bill_committee_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id uuid NOT NULL REFERENCES core.bill(bill_id),
  namespace text NOT NULL DEFAULT 'congress.gov.committee',
  external_id text NOT NULL,
  name text,
  chamber text,
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  source_member text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE NULLS NOT DISTINCT (bill_id, namespace, external_id, source_artifact_id, source_member),
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS core.bill_subject (
  bill_subject_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id uuid NOT NULL REFERENCES core.bill(bill_id),
  namespace text NOT NULL DEFAULT 'congress.gov.subject',
  external_id text NOT NULL,
  label text NOT NULL,
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  source_member text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE NULLS NOT DISTINCT (bill_id, namespace, external_id, source_artifact_id, source_member),
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS core.bill_document (
  bill_document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id uuid NOT NULL REFERENCES core.bill(bill_id),
  document_type text NOT NULL,
  version_code text,
  title text,
  published_at timestamptz,
  source_url text NOT NULL,
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  source_member text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE NULLS NOT DISTINCT (bill_id, document_type, version_code, source_url, source_artifact_id, source_member),
  CHECK (source_artifact_id IS NOT NULL OR source_payload_id IS NOT NULL)
);
