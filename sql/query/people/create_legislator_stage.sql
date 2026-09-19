CREATE TEMP TABLE legislator_stage (
  bioguide text NOT NULL,
  new_person_id uuid NOT NULL,
  full_name text NOT NULL,
  given_name text,
  family_name text,
  namespace text NOT NULL,
  external_id text NOT NULL,
  artifact_id uuid NOT NULL,
  run_id uuid NOT NULL
) ON COMMIT DROP
