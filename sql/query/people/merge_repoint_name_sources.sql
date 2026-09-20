-- Repoint the duplicate's name assertions to the survivor, except those the survivor already
-- asserts (same kind, dataset and vintage): the survivor's own stands, the rest are moved.
UPDATE core.person_name_source d
SET person_id = %(survivor)s, updated_at = now()
WHERE d.person_id = %(duplicate)s
  AND NOT EXISTS (
    SELECT 1 FROM core.person_name_source s
    WHERE s.person_id = %(survivor)s AND s.name_kind = d.name_kind
      AND s.dataset_id = d.dataset_id AND s.source_vintage = d.source_vintage)
