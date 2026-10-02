WITH raw_values AS (SELECT {column}::text AS raw FROM {relation}), classified AS (
  SELECT raw, CASE
    WHEN raw IS NULL THEN 'sql_null'
    WHEN btrim(raw)='' THEN 'blank'
    WHEN raw ~ '^[0-9]{{4}}$' AND pg_input_is_valid(raw||'-01-01','date') THEN 'year'
    WHEN raw ~ '^[0-9]{{4}}-[0-9]{{2}}$' AND pg_input_is_valid(raw||'-01','date') THEN 'month'
    WHEN raw ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' AND pg_input_is_valid(raw,'date') THEN 'day'
    ELSE 'invalid_or_unsupported'
  END AS precision FROM raw_values
)
SELECT precision, count(*) AS row_count,
       min(raw) FILTER (WHERE precision IN ('year','month','day')) AS minimum,
       max(raw) FILTER (WHERE precision IN ('year','month','day')) AS maximum
FROM classified GROUP BY precision ORDER BY precision;
