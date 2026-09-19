-- Older versions of one logical artifact: the versions a load of %(artifact_id)s supersedes.
-- Strictly older, so a newer version is never touched by loading this one.
SELECT older.artifact_id
FROM ingest.artifact AS kept
JOIN ingest.artifact AS older
  ON older.dataset_id = kept.dataset_id
 AND older.artifact_key = kept.artifact_key
 AND older.artifact_version < kept.artifact_version
WHERE kept.artifact_id = %(artifact_id)s;
