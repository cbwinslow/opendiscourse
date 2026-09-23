-- Drop Voteview name notes the current member file no longer supports.
-- Other kinds and datasets stay, and nothing here writes the displayed name.
DELETE FROM core.person_name_source AS n
WHERE n.dataset_id = %(dataset_id)s
  AND n.name_kind = 'voteview'
  AND NOT EXISTS (
    SELECT 1
    FROM jsonb_to_recordset(%(kept)s::jsonb) AS k(person_id uuid, source_vintage text)
    WHERE k.person_id = n.person_id
      AND k.source_vintage = n.source_vintage
  )
RETURNING 1
