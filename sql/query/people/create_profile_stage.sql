CREATE TEMP TABLE profile_person (
  bioguide text NOT NULL,
  source_file text NOT NULL,
  artifact_id uuid NOT NULL,
  run_id uuid NOT NULL,
  birthday date,
  gender text,
  record jsonb NOT NULL
) ON COMMIT DROP;

CREATE TEMP TABLE profile_leadership (
  bioguide text NOT NULL,
  chamber text NOT NULL,
  title text NOT NULL,
  start_date date NOT NULL,
  end_date date,
  artifact_id uuid NOT NULL,
  run_id uuid NOT NULL
) ON COMMIT DROP;

CREATE TEMP TABLE profile_social (
  bioguide text NOT NULL,
  network text NOT NULL,
  handle text,
  external_id text,
  artifact_id uuid NOT NULL,
  run_id uuid NOT NULL,
  record jsonb NOT NULL
) ON COMMIT DROP;

CREATE TEMP TABLE profile_office (
  bioguide text NOT NULL,
  office_key text NOT NULL,
  address text,
  building text,
  suite text,
  city text,
  state text,
  zip text,
  phone text,
  fax text,
  hours text,
  latitude double precision,
  longitude double precision,
  artifact_id uuid NOT NULL,
  run_id uuid NOT NULL,
  record jsonb NOT NULL
) ON COMMIT DROP;

CREATE TEMP TABLE profile_name (
  bioguide text NOT NULL,
  name_kind text NOT NULL,
  full_name text NOT NULL,
  given_name text,
  family_name text,
  source_vintage text NOT NULL,
  artifact_id uuid NOT NULL,
  run_id uuid NOT NULL
) ON COMMIT DROP;

CREATE TEMP TABLE profile_source (
  source_file text NOT NULL,
  member_key text NOT NULL,
  bioguide text NOT NULL,
  record jsonb NOT NULL,
  artifact_id uuid NOT NULL,
  run_id uuid NOT NULL
) ON COMMIT DROP;
