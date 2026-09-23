-- Replace every Voteview roll call from one file. The official vote is linked
-- only when exactly one core.roll_call matches, and that vote is not updated.
-- House and Senate use the same key: Congress + chamber + session (1st/2nd)
-- + Voteview clerk_rollnumber. Voteview's own rollnumber is not that number.
-- No clerk number, or any session other than 1 or 2, is no link. Two matches
-- is no link. Keep this predicate in step with summary.sql.
WITH incoming AS (
  SELECT r.*, link.matches, link.roll_call_id
  FROM jsonb_to_recordset(%(rows)s::jsonb) AS r(
    congress integer,
    chamber text,
    rollnumber integer,
    session integer,
    clerk_rollnumber integer,
    vote_date date,
    majority_requirement text,
    yea_count integer,
    nay_count integer,
    nominate_mid_1 double precision,
    nominate_mid_2 double precision,
    nominate_spread_1 double precision,
    nominate_spread_2 double precision,
    nominate_log_likelihood double precision,
    bill_number text,
    vote_result text,
    vote_desc text,
    vote_question text,
    dtl_desc text,
    issue_codes jsonb,
    peltzman_codes jsonb,
    clausen_codes jsonb,
    crs_policy_area text,
    crs_subjects jsonb,
    congress_url text,
    source_documents jsonb,
    record jsonb,
    source_artifact_id uuid,
    run_id uuid
  )
  LEFT JOIN LATERAL (
    SELECT count(*) AS matches,
           CASE WHEN count(*) = 1 THEN min(rc.roll_call_id::text)::uuid ELSE NULL END AS roll_call_id
    FROM core.roll_call AS rc
    WHERE rc.jurisdiction = 'us'
      AND rc.legislative_session = r.congress::text
      AND rc.chamber = r.chamber
      AND r.clerk_rollnumber IS NOT NULL
      AND (
        (r.session = 1 AND rc.congress_session = '1st')
        OR (r.session = 2 AND rc.congress_session = '2nd')
      )
      AND rc.roll_number = r.clerk_rollnumber
  ) AS link ON true
), inserted AS (
  INSERT INTO core.voteview_roll_call (
    congress, chamber, rollnumber, session, clerk_rollnumber, vote_date,
    majority_requirement, yea_count, nay_count, nominate_mid_1, nominate_mid_2,
    nominate_spread_1, nominate_spread_2, nominate_log_likelihood, bill_number,
    vote_result, vote_desc, vote_question, dtl_desc, issue_codes, peltzman_codes,
    clausen_codes, crs_policy_area, crs_subjects, congress_url, source_documents,
    roll_call_id, record, source_artifact_id, run_id
  )
  SELECT
    congress, chamber, rollnumber, session, clerk_rollnumber, vote_date,
    majority_requirement, yea_count, nay_count, nominate_mid_1, nominate_mid_2,
    nominate_spread_1, nominate_spread_2, nominate_log_likelihood, bill_number,
    vote_result, vote_desc, vote_question, dtl_desc, issue_codes, peltzman_codes,
    clausen_codes, crs_policy_area, crs_subjects, congress_url, source_documents,
    CASE WHEN matches = 1 THEN roll_call_id ELSE NULL END,
    record, source_artifact_id, run_id
  FROM incoming
  RETURNING 1
)
SELECT count(*) AS inserted FROM inserted
