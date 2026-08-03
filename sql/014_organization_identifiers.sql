CREATE TABLE IF NOT EXISTS core.organization_identifier (
  organization_id uuid NOT NULL REFERENCES core.organization(organization_id),
  namespace text NOT NULL,
  external_id text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  PRIMARY KEY (namespace, external_id)
);
