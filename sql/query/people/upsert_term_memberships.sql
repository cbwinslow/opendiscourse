-- One membership per term. A rerun with the same bytes changes nothing; an edited end date, party
-- or post updates the row and moves its evidence to the artifact that now asserts it.
INSERT INTO core.membership (
  person_id, organization_id, post_id, role, start_date, end_date, source_artifact_id, metadata,
  office, address, phone, fax, contact_form, url, rss_url
)
SELECT DISTINCT ON (person_id, organization_id, role, start_date)
       person_id, organization_id, post_id, role, start_date, end_date, artifact_id, metadata,
       office, address, phone, fax, contact_form, url, rss_url
FROM (
  SELECT pi.person_id,
         CASE s.chamber WHEN 'rep' THEN %(house)s::uuid ELSE %(senate)s::uuid END AS organization_id,
         p.post_id, s.role, s.start_date, s.end_date, s.artifact_id, s.metadata,
         NULLIF(s.contact->>'office', '') AS office,
         NULLIF(s.contact->>'address', '') AS address,
         NULLIF(s.contact->>'phone', '') AS phone,
         NULLIF(s.contact->>'fax', '') AS fax,
         NULLIF(s.contact->>'contact_form', '') AS contact_form,
         NULLIF(s.contact->>'url', '') AS url,
         NULLIF(s.contact->>'rss_url', '') AS rss_url
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
  metadata = EXCLUDED.metadata,
  office = EXCLUDED.office,
  address = EXCLUDED.address,
  phone = EXCLUDED.phone,
  fax = EXCLUDED.fax,
  contact_form = EXCLUDED.contact_form,
  url = EXCLUDED.url,
  rss_url = EXCLUDED.rss_url
WHERE (
  core.membership.post_id, core.membership.end_date, core.membership.source_artifact_id,
  core.membership.metadata, core.membership.office, core.membership.address, core.membership.phone,
  core.membership.fax, core.membership.contact_form, core.membership.url, core.membership.rss_url
) IS DISTINCT FROM (
  EXCLUDED.post_id, EXCLUDED.end_date, EXCLUDED.source_artifact_id, EXCLUDED.metadata,
  EXCLUDED.office, EXCLUDED.address, EXCLUDED.phone, EXCLUDED.fax, EXCLUDED.contact_form,
  EXCLUDED.url, EXCLUDED.rss_url
)
RETURNING (xmax = 0) AS inserted
