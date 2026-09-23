-- Voteview name notes already stored, so a second load of the same bytes writes none.
SELECT person_id::text AS person_id,
       source_vintage,
       full_name,
       given_name,
       family_name,
       artifact_id::text AS artifact_id
FROM core.person_name_source
WHERE dataset_id = %(dataset_id)s
  AND name_kind = 'voteview'
