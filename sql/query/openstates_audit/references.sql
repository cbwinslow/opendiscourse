SELECT count(*) AS unresolved_count FROM {source} s
WHERE {nonnull} AND NOT EXISTS (SELECT 1 FROM {target} t WHERE {matches});
