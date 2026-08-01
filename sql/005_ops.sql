CREATE TABLE IF NOT EXISTS catalog.plan (
  plan_id text PRIMARY KEY,
  dataset_id text NOT NULL REFERENCES catalog.dataset(dataset_id),
  handler text NOT NULL,
  cadence text NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingest.cursor (
  plan_id text PRIMARY KEY REFERENCES catalog.plan(plan_id),
  cursor jsonb NOT NULL DEFAULT '{}'::jsonb,
  successful_run_id uuid REFERENCES ingest.run(run_id),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS core.document (
  document_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_type text NOT NULL,
  source_key text NOT NULL,
  title text,
  published_at timestamptz,
  language text NOT NULL DEFAULT 'en',
  canonical_url text,
  checksum_sha256 text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_payload_id uuid REFERENCES ingest.raw_payload(payload_id),
  artifact_id uuid REFERENCES ingest.artifact(artifact_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_type, source_key)
);

CREATE TABLE IF NOT EXISTS core.bill_document (
  bill_id uuid NOT NULL REFERENCES core.bill(bill_id),
  document_id uuid NOT NULL REFERENCES core.document(document_id),
  relation text NOT NULL DEFAULT 'text',
  PRIMARY KEY (bill_id, document_id, relation)
);

CREATE TABLE IF NOT EXISTS core.document_chunk (
  chunk_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES core.document(document_id),
  ordinal integer NOT NULL CHECK (ordinal >= 0),
  text text NOT NULL,
  token_count integer,
  checksum_sha256 text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (document_id, ordinal),
  UNIQUE (document_id, checksum_sha256)
);

-- Arrays keep the base image portable.  A production vector-search deployment
-- can add pgvector and a generated/vector column without rewriting documents.
CREATE TABLE IF NOT EXISTS core.embedding (
  embedding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_id uuid NOT NULL REFERENCES core.document_chunk(chunk_id),
  model text NOT NULL,
  dimensions integer NOT NULL CHECK (dimensions > 0),
  vector_values real[] NOT NULL,
  CHECK (cardinality(vector_values) = dimensions),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (chunk_id, model)
);
