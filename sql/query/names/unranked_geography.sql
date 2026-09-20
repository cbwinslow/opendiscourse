-- Geography assertions the precedence file cannot place, one row per (dataset, kind, type) with the
-- first reason that applies: the dataset is ranked nowhere, the kind is ranked or displayed nowhere,
-- the geography type is ranked nowhere, or this dataset is not ranked for this kind and type.
-- Empty means every assertion has a rank.
SELECT CASE
         WHEN NOT EXISTS (SELECT 1 FROM catalog.attribute_precedence p
                          WHERE p.entity = 'geography' AND p.dataset_id = a.dataset_id) THEN 'dataset'
         WHEN NOT EXISTS (SELECT 1 FROM catalog.attribute_precedence p
                          WHERE p.entity = 'geography' AND p.name_kind = a.name_kind)
           OR NOT EXISTS (SELECT 1 FROM catalog.name_display d
                          WHERE d.entity = 'geography' AND d.name_kind = a.name_kind) THEN 'name_kind'
         WHEN NOT EXISTS (SELECT 1 FROM catalog.attribute_precedence p
                          WHERE p.entity = 'geography' AND p.geography_type = a.geography_type) THEN 'geography_type'
         ELSE 'dataset_kind'
       END AS reason,
       a.dataset_id, a.name_kind, a.geography_type, a.assertions
FROM (
  SELECT s.dataset_id, s.name_kind, g.geography_type, count(*) AS assertions
  FROM core.geography_name_source s
  JOIN core.geography g ON g.geography_id = s.geography_id
  GROUP BY s.dataset_id, s.name_kind, g.geography_type
) AS a
WHERE NOT EXISTS (
        SELECT 1 FROM catalog.attribute_precedence p
        WHERE p.entity = 'geography' AND p.name_kind = a.name_kind
          AND p.geography_type = a.geography_type AND p.dataset_id = a.dataset_id)
   OR NOT EXISTS (
        SELECT 1 FROM catalog.name_display d
        WHERE d.entity = 'geography' AND d.name_kind = a.name_kind)
ORDER BY a.dataset_id COLLATE "C", a.name_kind COLLATE "C", a.geography_type COLLATE "C"
