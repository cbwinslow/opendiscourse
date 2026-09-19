CREATE TEMP TABLE term_stage (
  bioguide text NOT NULL,
  artifact_id uuid NOT NULL,
  chamber text NOT NULL,
  role text NOT NULL,
  start_date date NOT NULL,
  end_date date NOT NULL,
  state_ocd text NOT NULL,
  state_label text NOT NULL,
  state_class text NOT NULL,
  post_ocd text,
  post_division_label text,
  post_division_class text,
  post_label text,
  post_role text,
  metadata jsonb NOT NULL
) ON COMMIT DROP
