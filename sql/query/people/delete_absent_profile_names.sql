DELETE FROM core.person_name_source AS n
WHERE n.dataset_id = 'congress.legislators'
  AND n.name_kind IN ('official', 'middle', 'suffix', 'nickname', 'former')
  AND NOT EXISTS (
    SELECT 1
    FROM profile_name AS s
    JOIN core.person_identifier AS pi
      ON pi.namespace = 'bioguide' AND pi.external_id = s.bioguide
    WHERE pi.person_id = n.person_id
      AND s.name_kind = n.name_kind
      AND s.source_vintage = n.source_vintage
  )
RETURNING 1
