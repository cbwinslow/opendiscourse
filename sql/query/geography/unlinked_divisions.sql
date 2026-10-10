-- Divisions of a linkable family that reached no boundary of this vintage, with the reason
-- a reviewer needs: historical (district number beyond the current plan) or label not numeric.
SELECT division.ocd_division_id,
       CASE WHEN division.ocd_division_id ~ '/(sldu|sldl):[0-9]+$' THEN 'no_matching_boundary'
            WHEN division.ocd_division_id ~ '/(sldu|sldl):' THEN 'non_numeric_label_needs_reviewed_mapping'
            ELSE 'not_in_current_plan' END AS reason
FROM core.division AS division
WHERE division.ocd_division_id ~ '/cd:|/(sldu|sldl):'
  AND NOT EXISTS (SELECT 1 FROM core.division_boundary AS link WHERE link.division_id = division.division_id)
ORDER BY 1;
