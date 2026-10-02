SELECT count(*) AS row_count, count(*) FILTER (WHERE {column} IS NULL) AS null_count,
       count(DISTINCT to_jsonb({column})) AS distinct_count FROM {relation};
