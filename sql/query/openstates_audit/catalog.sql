SELECT n.nspname AS source_schema, c.relname AS source_table, c.relkind,
       c.relrowsecurity AS row_security,
       has_schema_privilege(n.oid, 'USAGE') AND has_table_privilege(c.oid, 'SELECT') AS selectable,
       e.extname AS extension
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_catalog.pg_depend d ON d.classid = 'pg_class'::regclass
  AND d.objid = c.oid AND d.deptype = 'e'
LEFT JOIN pg_catalog.pg_extension e ON e.oid = d.refobjid
WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
ORDER BY n.nspname, c.relname;
