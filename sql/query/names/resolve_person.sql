-- Show each person the winning assertion: the first displayed kind that has one, then the best
-- ranked dataset, then the newest vintage, then dataset id and value. Every tie-break is
-- COLLATE "C" so the answer never depends on a uuid, insertion order or database collation.
-- The full/given/family triple always comes from the one winning assertion. Rows are locked in
-- primary-key order and only rows whose result differs are updated; old values are reported too.
WITH winner AS (
  SELECT DISTINCT ON (s.person_id)
         s.person_id, s.person_name_source_id, s.full_name, s.given_name, s.family_name
  FROM core.person_name_source s
  JOIN catalog.name_display d ON d.entity = 'person' AND d.name_kind = s.name_kind
  JOIN catalog.attribute_precedence p
    ON p.entity = 'person' AND p.name_kind = s.name_kind AND p.geography_type = '' AND p.dataset_id = s.dataset_id
  ORDER BY s.person_id, d.position, p.rank, s.source_vintage COLLATE "C" DESC,
           s.dataset_id COLLATE "C", s.full_name COLLATE "C"
), changed AS (
  SELECT c.person_id, c.full_name AS old_full_name, c.given_name AS old_given_name,
         c.family_name AS old_family_name, c.name_source_id AS old_name_source_id,
         w.person_name_source_id, w.full_name, w.given_name, w.family_name
  FROM core.person c
  JOIN winner w ON w.person_id = c.person_id
  WHERE (c.full_name, c.given_name, c.family_name, c.name_source_id)
        IS DISTINCT FROM (w.full_name, w.given_name, w.family_name, w.person_name_source_id)
  ORDER BY c.person_id
  FOR UPDATE OF c
)
UPDATE core.person p
SET full_name = ch.full_name, given_name = ch.given_name, family_name = ch.family_name,
    name_source_id = ch.person_name_source_id
FROM changed ch
WHERE p.person_id = ch.person_id
RETURNING p.person_id,
          ch.old_full_name, ch.old_given_name, ch.old_family_name, ch.old_name_source_id,
          p.full_name, p.given_name, p.family_name, p.name_source_id
