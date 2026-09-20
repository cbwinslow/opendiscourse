-- Link Senate roll calls to the bills their document names, for the ones not linked yet. Runs at the
-- end of a sync so a bill loaded after its roll call still gets linked on the next run. By Congress,
-- type and number only: the document type is one of the eight bill types (a nomination, a treaty or
-- an amendment has none), and a bill that core.bill does not hold leaves the roll call unlinked.
-- document_congress is the Congress the file states; older files omit it and mean the roll call's own.
UPDATE core.roll_call r
SET bill_id = b.bill_id
FROM core.bill b
WHERE r.chamber = 'senate' AND r.jurisdiction = 'us' AND r.bill_id IS NULL
  AND r.legislative_session = ANY(%(congresses)s::text[])
  AND r.document_number ~ '^[0-9]+$'
  AND b.jurisdiction = 'us'
  AND b.legislative_session = COALESCE(r.document_congress::text, r.legislative_session)
  AND b.bill_number = r.document_number
  AND b.bill_type = CASE r.document_type
    WHEN 'H.R.' THEN 'hr' WHEN 'S.' THEN 's' WHEN 'H.Res.' THEN 'hres' WHEN 'S.Res.' THEN 'sres'
    WHEN 'H.Con.Res.' THEN 'hconres' WHEN 'S.Con.Res.' THEN 'sconres'
    WHEN 'H.J.Res.' THEN 'hjres' WHEN 'S.J.Res.' THEN 'sjres'
  END;
