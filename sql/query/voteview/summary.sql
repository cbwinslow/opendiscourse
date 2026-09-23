-- Read-only counts after a load (or a rerun that wrote nothing).
-- The roll-call predicate matches replace_roll_calls.sql. Official votes are not updated.
WITH members AS (
  SELECT m.*, owners.people, bios.bioguides
  FROM core.voteview_member AS m
  LEFT JOIN LATERAL (
    SELECT array_agg(DISTINCT person_id) AS people
    FROM core.person_identifier
    WHERE namespace = 'icpsr' AND external_id = m.icpsr
  ) AS owners ON true
  LEFT JOIN LATERAL (
    SELECT array_agg(DISTINCT external_id) AS bioguides
    FROM core.person_identifier
    WHERE namespace = 'bioguide'
      AND cardinality(owners.people) = 1
      AND person_id = (owners.people)[1]
  ) AS bios ON true
), rolls AS (
  SELECT v.chamber, v.clerk_rollnumber, link.matches
  FROM core.voteview_roll_call AS v
  LEFT JOIN LATERAL (
    SELECT count(*) AS matches
    FROM core.roll_call AS rc
    WHERE rc.jurisdiction = 'us'
      AND rc.legislative_session = v.congress::text
      AND rc.chamber = v.chamber
      AND v.clerk_rollnumber IS NOT NULL
      AND (
        (v.session = 1 AND rc.congress_session = '1st')
        OR (v.session = 2 AND rc.congress_session = '2nd')
      )
      AND rc.roll_number = v.clerk_rollnumber
  ) AS link ON true
)
SELECT
  (SELECT count(*) FROM core.voteview_member) AS members,
  (SELECT count(*) FROM core.voteview_roll_call) AS roll_calls,
  (SELECT count(*) FROM core.voteview_party) AS parties,
  (SELECT count(*) FROM members
    WHERE chamber IN ('house', 'senate') AND person_id IS NULL) AS unlinked_members,
  (SELECT count(*) FROM members
    WHERE chamber = 'president' AND person_id IS NULL) AS unlinked_presidents,
  (SELECT count(*) FROM members
    WHERE cardinality(people) = 1
      AND bioguide IS NOT NULL AND btrim(bioguide) <> ''
      AND bioguides IS NOT NULL
      AND NOT (bioguide = ANY (bioguides))) AS bioguide_disagreements,
  (SELECT count(*) FROM rolls WHERE matches = 1) AS votes_linked,
  (SELECT count(*) FROM rolls WHERE matches > 1) AS votes_ambiguous,
  (SELECT count(*) FROM rolls
    WHERE matches = 0 AND clerk_rollnumber IS NULL) AS votes_no_clerk_number,
  (SELECT count(*) FROM rolls
    WHERE matches = 0 AND clerk_rollnumber IS NOT NULL) AS votes_unmatched
