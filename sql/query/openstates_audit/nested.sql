WITH RECURSIVE nodes(path, value, weight) AS (
  SELECT '[]'::jsonb, to_jsonb({column}), count(*)
  FROM {relation} WHERE {column} IS NOT NULL GROUP BY to_jsonb({column})
  UNION ALL
  SELECT n.path || child.step, child.value, n.weight
  FROM nodes n CROSS JOIN LATERAL (
    SELECT jsonb_build_array(jsonb_build_object('kind','key','value',key)) AS step, value FROM jsonb_each(CASE WHEN jsonb_typeof(n.value)='object' THEN n.value ELSE '{{}}'::jsonb END)
    UNION ALL
    SELECT '[{{"kind":"array_element"}}]'::jsonb, value FROM jsonb_array_elements(CASE WHEN jsonb_typeof(n.value)='array' THEN n.value ELSE '[]'::jsonb END)
  ) child
)
SELECT path, jsonb_typeof(value) AS source_type, sum(weight)::bigint AS occurrence_count,
       COALESCE(sum(sum(weight)) FILTER (WHERE jsonb_typeof(value)='null')
         OVER (PARTITION BY path), 0)::double precision /
         sum(sum(weight)) OVER (PARTITION BY path) AS null_rate,
       'present_path_occurrences; absent paths are not nulls' AS null_rate_scope
FROM nodes GROUP BY path, jsonb_typeof(value) ORDER BY path, source_type;
