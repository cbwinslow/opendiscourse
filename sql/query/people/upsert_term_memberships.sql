-- One membership per term. A rerun with the same bytes changes nothing; an edited end date, party
-- or post updates the row and moves its evidence to the artifact that now asserts it.
INSERT INTO core.membership (
  person_id, organization_id, post_id, role, start_date, end_date, source_artifact_id, metadata
)
SELECT DISTINCT ON (person_id, organization_id, role, start_date)
       person_id, organization_id, post_id, role, start_date, end_date, artifact_id, metadata
FROM (
  SELECT pi.person_id,
         CASE s.chamber WHEN 'rep' THEN %(house)s::uuid ELSE %(senate)s::uuid END AS organization_id,
         p.post_id, s.role, s.start_date, s.end_date, s.artifact_id, s.metadata
  FROM term_stage AS s
  JOIN core.person_identifier AS pi ON pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
  LEFT JOIN core.division AS d ON d.ocd_division_id = s.post_ocd
  LEFT JOIN core.post AS p
    ON p.division_id = d.division_id
   AND p.label = s.post_label
   AND p.organization_id = CASE s.chamber WHEN 'rep' THEN %(house)s::uuid ELSE %(senate)s::uuid END
) AS terms
ORDER BY person_id, organization_id, role, start_date, artifact_id
ON CONFLICT (person_id, organization_id, role, start_date) WHERE source_artifact_id IS NOT NULL
DO UPDATE SET
  post_id = EXCLUDED.post_id,
  end_date = EXCLUDED.end_date,
  source_artifact_id = EXCLUDED.source_artifact_id,
  metadata = EXCLUDED.metadata
WHERE (core.membership.post_id, core.membership.end_date, core.membership.source_artifact_id, core.membership.metadata)
  IS DISTINCT FROM (EXCLUDED.post_id, EXCLUDED.end_date, EXCLUDED.source_artifact_id, EXCLUDED.metadata)
RETURNING (xmax = 0) AS inserted
