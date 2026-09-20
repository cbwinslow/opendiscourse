-- Show each geography the winning assertion: the first displayed kind that has one, then the best
-- ranked dataset for the geography's type, then the newest vintage, then dataset id and value, all
-- COLLATE "C". Rows are locked in primary-key order and only rows whose result differs are updated;
-- old values are reported too.
WITH winner AS (
  SELECT DISTINCT ON (s.geography_id)
         s.geography_id, s.geography_name_source_id, s.name
  FROM core.geography_name_source s
  JOIN core.geography g ON g.geography_id = s.geography_id
  JOIN catalog.name_display d ON d.entity = 'geography' AND d.name_kind = s.name_kind
  JOIN catalog.attribute_precedence p
    ON p.entity = 'geography' AND p.name_kind = s.name_kind
   AND p.geography_type = g.geography_type AND p.dataset_id = s.dataset_id
  ORDER BY s.geography_id, d.position, p.rank, s.source_vintage COLLATE "C" DESC,
           s.dataset_id COLLATE "C", s.name COLLATE "C"
), changed AS (
  SELECT c.geography_id, c.geography_type, c.geoid, c.name AS old_name, c.name_source_id AS old_name_source_id,
         w.geography_name_source_id, w.name
  FROM core.geography c
  JOIN winner w ON w.geography_id = c.geography_id
  WHERE (c.name, c.name_source_id) IS DISTINCT FROM (w.name, w.geography_name_source_id)
  ORDER BY c.geography_id
  FOR UPDATE OF c
)
UPDATE core.geography g
SET name = ch.name, name_source_id = ch.geography_name_source_id
FROM changed ch
WHERE g.geography_id = ch.geography_id
RETURNING g.geography_id, ch.geography_type, ch.geoid, ch.old_name, ch.old_name_source_id,
          g.name, g.name_source_id
