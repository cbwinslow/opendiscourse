-- Every state, territory and district a staged term names. An id already known is left alone.
INSERT INTO core.division (ocd_division_id, label, classification, source_artifact_id)
SELECT DISTINCT ON (ocd) ocd, label, classification, artifact_id
FROM (
  SELECT state_ocd AS ocd, state_label AS label, state_class AS classification, artifact_id
  FROM term_stage
  UNION ALL
  SELECT post_ocd, post_division_label, post_division_class, artifact_id
  FROM term_stage
  WHERE post_ocd IS NOT NULL
) AS wanted
ORDER BY ocd, artifact_id
ON CONFLICT (ocd_division_id) WHERE ocd_division_id IS NOT NULL DO NOTHING
