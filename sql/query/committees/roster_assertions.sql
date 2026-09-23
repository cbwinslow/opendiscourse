SELECT person_id::text AS person_id, full_name, artifact_id::text AS artifact_id,
       given_name, family_name
FROM core.person_name_source
WHERE dataset_id = %(dataset_id)s
  AND name_kind = 'roster'
  AND source_vintage = %(vintage)s
