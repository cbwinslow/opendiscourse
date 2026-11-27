-- A listed term replaces an unlisted one it overlaps (same member, chamber and role): the
-- publisher corrected the start date, which is part of a term's identity, so the upsert added a
-- second row. An unlisted term that no listed term overlaps is kept. Terms may share a boundary day.
-- Run after upsert_term_memberships, which moves every listed term onto an artifact of this load:
-- a legislator term on any other artifact is unlisted. That narrows 45,000 rows to a few before
-- the overlap join (comparing every row took 126 s on the live warehouse).
WITH unlisted AS MATERIALIZED (
  SELECT m.membership_id, m.person_id, m.organization_id, m.role, m.start_date, m.end_date
  FROM core.membership AS m
  JOIN ingest.artifact AS a
    ON a.artifact_id = m.source_artifact_id AND a.dataset_id = 'congress.legislators'
  WHERE m.source_artifact_id NOT IN (SELECT DISTINCT artifact_id FROM term_stage)  -- never null
), superseded AS (
  SELECT u.membership_id, min(s.bioguide) AS bioguide, min(s.start_date) AS replaced_by_start
  FROM unlisted AS u
  JOIN core.person_identifier AS pi ON pi.person_id = u.person_id AND pi.namespace = 'bioguide'
  JOIN term_stage AS s
    ON s.bioguide = pi.external_id AND s.role = u.role
   AND CASE s.chamber WHEN 'rep' THEN %(house)s::uuid ELSE %(senate)s::uuid END = u.organization_id
   AND s.start_date < u.end_date AND s.end_date > u.start_date
  GROUP BY u.membership_id
)
DELETE FROM core.membership AS m
USING superseded AS s
WHERE m.membership_id = s.membership_id
RETURNING s.bioguide, m.role, m.start_date, m.end_date, s.replaced_by_start
