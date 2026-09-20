-- Name assertions of the duplicate whose natural key the survivor already asserts. The survivor's
-- stays; these are dropped with the duplicate and counted.
SELECT count(*) AS collisions
FROM core.person_name_source d
JOIN core.person_name_source s
  ON s.person_id = %(survivor)s AND s.name_kind = d.name_kind
 AND s.dataset_id = d.dataset_id AND s.source_vintage = d.source_vintage
WHERE d.person_id = %(duplicate)s
