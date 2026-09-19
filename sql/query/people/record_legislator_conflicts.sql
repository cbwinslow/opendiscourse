-- Groups the source asserts but the warehouse cannot place without guessing. Recorded
-- once per (record, kind, owners); a rerun only bumps seen_count. Returned for the report.
INSERT INTO ingest.identity_conflict (dataset_id, run_id, kind, subject, person_ids, identifiers)
SELECT 'congress.legislators', r.run_id, g.outcome, 'bioguide:' || g.bioguide, g.owner_ids,
       (SELECT jsonb_agg(jsonb_build_array(s.namespace, s.external_id) ORDER BY s.namespace, s.external_id)
        FROM legislator_stage s WHERE s.bioguide = g.bioguide)
FROM legislator_group g
JOIN (SELECT DISTINCT ON (bioguide) bioguide, run_id FROM legislator_stage ORDER BY bioguide) r USING (bioguide)
WHERE g.outcome IN ('multiple_owners', 'bioguide_mismatch')
ON CONFLICT (dataset_id, kind, subject, person_ids) DO UPDATE
  SET seen_count = ingest.identity_conflict.seen_count + 1,
      last_seen_at = now(),
      resolved_at = NULL,
      resolution = NULL,
      run_id = EXCLUDED.run_id,
      identifiers = EXCLUDED.identifiers
RETURNING subject, kind, person_ids
