SELECT n.nspname AS reader_schema, c.relname AS reader_table,
       COALESCE((SELECT option_value FROM pg_options_to_table(f.ftoptions) WHERE option_name='schema_name'), 'public') AS source_schema,
       COALESCE((SELECT option_value FROM pg_options_to_table(f.ftoptions) WHERE option_name='table_name'), c.relname) AS source_table,
       has_schema_privilege(n.oid, 'USAGE') AND has_table_privilege(c.oid, 'SELECT') AS selectable
FROM pg_catalog.pg_foreign_table f
JOIN pg_catalog.pg_class c ON c.oid = f.ftrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s ORDER BY c.relname;
