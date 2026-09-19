-- A refreshed BILLSTATUS zip is a new artifact version, and each child table keys its
-- rows on source_artifact_id, so loading it beside the old version would duplicate every
-- action, sponsorship, committee and subject. Drop the older versions' rows for exactly
-- the bills the new version just rewrote, in the same transaction.
WITH actions AS (
  DELETE FROM core.bill_action
  WHERE bill_id = ANY(%(bill_ids)s::uuid[]) AND source_artifact_id = ANY(%(old_artifact_ids)s::uuid[])
  RETURNING 1
), sponsorships AS (
  DELETE FROM core.bill_sponsorship
  WHERE bill_id = ANY(%(bill_ids)s::uuid[]) AND source_artifact_id = ANY(%(old_artifact_ids)s::uuid[])
  RETURNING 1
), committees AS (
  DELETE FROM core.bill_committee
  WHERE bill_id = ANY(%(bill_ids)s::uuid[]) AND source_artifact_id = ANY(%(old_artifact_ids)s::uuid[])
  RETURNING 1
), subjects AS (
  DELETE FROM core.bill_subject
  WHERE bill_id = ANY(%(bill_ids)s::uuid[]) AND source_artifact_id = ANY(%(old_artifact_ids)s::uuid[])
  RETURNING 1
)
SELECT
  (SELECT count(*) FROM actions) AS actions,
  (SELECT count(*) FROM sponsorships) AS sponsorships,
  (SELECT count(*) FROM committees) AS committees,
  (SELECT count(*) FROM subjects) AS subjects;
