SELECT count(*)::bigint AS row_count
FROM stage.tiger_feature
WHERE artifact_id = %(artifact_id)s
  AND layer = %(layer)s;
