SELECT n.nspname AS source_schema, c.relname AS source_table,
       a.attname AS source_path, pg_catalog.format_type(a.atttypid, a.atttypmod) AS source_type,
       a.attnum AS position, a.attnotnull AS not_null
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
  AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY n.nspname, c.relname, a.attnum;
