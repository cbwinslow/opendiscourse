CREATE TABLE IF NOT EXISTS catalog.resource (
  resource_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  resource_key text NOT NULL,
  resource_type text NOT NULL,
  title text NOT NULL,
  summary text,
  universe text,
  release_year integer,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  discovered_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (dataset_id, resource_key)
);
CREATE INDEX IF NOT EXISTS resource_search_idx ON catalog.resource (dataset_id, release_year, resource_type);

CREATE TABLE IF NOT EXISTS catalog.resource_field (
  resource_id uuid NOT NULL REFERENCES catalog.resource(resource_id) ON DELETE CASCADE,
  field_key text NOT NULL,
  label text,
  description text,
  data_type text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  discovered_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (resource_id, field_key)
);

CREATE TABLE IF NOT EXISTS catalog.basket (
  basket_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  state text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'review', 'approved', 'archived')),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS catalog.basket_item (
  basket_id uuid NOT NULL REFERENCES catalog.basket(basket_id) ON DELETE CASCADE,
  resource_id uuid NOT NULL REFERENCES catalog.resource(resource_id) ON DELETE RESTRICT,
  selected_fields jsonb NOT NULL DEFAULT '[]'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  added_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (basket_id, resource_id)
);
