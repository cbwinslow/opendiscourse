-- Replace every Voteview party row from one file. Parties do not point at people.
WITH incoming AS (
  SELECT r.*
  FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(
    congress integer,
    chamber text,
    party_code integer,
    party_name text,
    n_members integer,
    nominate_dim1_median double precision,
    nominate_dim2_median double precision,
    nominate_dim1_mean double precision,
    nominate_dim2_mean double precision,
    record jsonb,
    source_artifact_id uuid,
    run_id uuid
  )
), inserted AS (
  INSERT INTO core.voteview_party (
    congress, chamber, party_code, party_name, n_members,
    nominate_dim1_median, nominate_dim2_median, nominate_dim1_mean, nominate_dim2_mean,
    record, source_artifact_id, run_id
  )
  SELECT
    congress, chamber, party_code, party_name, n_members,
    nominate_dim1_median, nominate_dim2_median, nominate_dim1_mean, nominate_dim2_mean,
    record, source_artifact_id, run_id
  FROM incoming
  RETURNING 1
)
SELECT count(*) AS inserted FROM inserted
