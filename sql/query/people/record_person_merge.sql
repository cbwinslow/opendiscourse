-- Written first so the preserved votes can reference it; counts are filled in at the end.
INSERT INTO ingest.person_merge (person_merge_id, exception_id, survivor_person_id, duplicate_person_id, counts, run_id)
VALUES (%(merge_id)s, %(exception_id)s, %(survivor)s, %(duplicate)s, '{}'::jsonb, %(run_id)s)
