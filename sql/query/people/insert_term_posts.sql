-- One post per chamber and place (state, district, seat class). Several members may share one.
INSERT INTO core.post (organization_id, division_id, label, role, source_artifact_id)
SELECT DISTINCT ON (organization_id, division_id, post_label)
       organization_id, division_id, post_label, post_role, artifact_id
FROM (
  SELECT CASE s.chamber WHEN 'rep' THEN %(house)s::uuid ELSE %(senate)s::uuid END AS organization_id,
         d.division_id, s.post_label, s.post_role, s.artifact_id
  FROM term_stage AS s
  JOIN core.division AS d ON d.ocd_division_id = s.post_ocd
  WHERE s.post_ocd IS NOT NULL
) AS wanted
ORDER BY organization_id, division_id, post_label, artifact_id
ON CONFLICT (organization_id, division_id, label) DO NOTHING
