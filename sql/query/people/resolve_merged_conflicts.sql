-- Conflicts that named the deleted duplicate are answered by the merge.
UPDATE ingest.identity_conflict
SET resolved_at = now(), resolution = %(resolution)s
WHERE %(duplicate)s = ANY(person_ids) AND resolved_at IS NULL
