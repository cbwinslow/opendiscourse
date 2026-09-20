-- Person assertions the precedence file cannot place, one row per (dataset, kind) with the first
-- reason that applies: the dataset is ranked nowhere, the kind is ranked or displayed nowhere, or
-- this dataset is not ranked for this kind. Empty means every assertion has a rank.
SELECT CASE
         WHEN NOT EXISTS (SELECT 1 FROM catalog.attribute_precedence p
                          WHERE p.entity = 'person' AND p.dataset_id = a.dataset_id) THEN 'dataset'
         WHEN NOT EXISTS (SELECT 1 FROM catalog.attribute_precedence p
                          WHERE p.entity = 'person' AND p.name_kind = a.name_kind)
           OR NOT EXISTS (SELECT 1 FROM catalog.name_display d
                          WHERE d.entity = 'person' AND d.name_kind = a.name_kind) THEN 'name_kind'
         ELSE 'dataset_kind'
       END AS reason,
       a.dataset_id, a.name_kind, NULL::text AS geography_type, a.assertions
FROM (
  SELECT s.dataset_id, s.name_kind, count(*) AS assertions
  FROM core.person_name_source s
  GROUP BY s.dataset_id, s.name_kind
) AS a
WHERE NOT EXISTS (
        SELECT 1 FROM catalog.attribute_precedence p
        WHERE p.entity = 'person' AND p.name_kind = a.name_kind
          AND p.geography_type = '' AND p.dataset_id = a.dataset_id)
   OR NOT EXISTS (
        SELECT 1 FROM catalog.name_display d
        WHERE d.entity = 'person' AND d.name_kind = a.name_kind)
ORDER BY a.dataset_id COLLATE "C", a.name_kind COLLATE "C"
