-- A file entry that is gone (a member who moved files, a dropped account, a closed office) is removed.
DELETE FROM core.legislator_source_record AS s
WHERE s.source_file = ANY(%(files)s)
  AND NOT EXISTS (
    SELECT 1
    FROM profile_source AS p
    WHERE p.source_file = s.source_file
      AND p.member_key = s.member_key
      AND p.bioguide = s.bioguide
  )
RETURNING 1
