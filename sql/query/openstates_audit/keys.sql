SELECT sn.nspname AS source_schema, s.relname AS source_table,
       con.conname AS constraint_name, con.contype AS kind, con.convalidated AS validated,
       ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(num, ord)
             JOIN pg_attribute a ON a.attrelid = s.oid AND a.attnum = k.num ORDER BY k.ord) AS columns,
       tn.nspname AS target_schema, t.relname AS target_table,
       ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY k(num, ord)
             JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.num ORDER BY k.ord) AS target_columns
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class s ON s.oid = con.conrelid
JOIN pg_catalog.pg_namespace sn ON sn.oid = s.relnamespace
LEFT JOIN pg_catalog.pg_class t ON t.oid = con.confrelid
LEFT JOIN pg_catalog.pg_namespace tn ON tn.oid = t.relnamespace
WHERE sn.nspname = ANY(%s) AND con.contype IN ('p', 'u', 'f')
ORDER BY sn.nspname, s.relname, con.conname;
