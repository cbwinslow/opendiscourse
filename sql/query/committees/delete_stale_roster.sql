-- Roster assertions are what the current file says about a linked person.
-- An empty id list removes every roster assertion for this dataset, including
-- one written under an older pin. Other kinds and datasets stay, and nothing
-- here writes the displayed name.
DELETE FROM core.person_name_source
WHERE dataset_id = %(dataset_id)s
  AND name_kind = 'roster'
  AND NOT EXISTS (
    SELECT 1
    FROM jsonb_array_elements_text(%(person_ids)s::jsonb) AS kept(person_id)
    WHERE kept.person_id::uuid = core.person_name_source.person_id
  )
RETURNING 1
