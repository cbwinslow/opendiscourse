WITH RECURSIVE objects(oid) AS (
  SELECT c.oid FROM pg_class c WHERE c.oid=to_regclass(%s)
  UNION
  SELECT d.refobjid FROM objects o JOIN pg_rewrite r ON r.ev_class=o.oid
  JOIN pg_depend d ON d.classid='pg_rewrite'::regclass AND d.objid=r.oid
  WHERE d.refclassid='pg_class'::regclass AND d.refobjid<>o.oid
)
SELECT n.nspname AS source_schema, c.relname AS source_table,
       pg_catalog.row_security_active(c.oid) AS filtered
FROM objects o JOIN pg_class c ON c.oid=o.oid JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind IN ('r','p') ORDER BY n.nspname,c.relname;
