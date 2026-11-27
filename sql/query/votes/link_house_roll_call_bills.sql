-- Link House roll calls to the bills the Clerk's own label names, for the ones not linked yet. Runs
-- at the end of a sync so a bill loaded after its roll call still gets linked on the next run. By
-- Congress, bill type and number only. The label is spaced capitals ("H R 498", "H CON RES 5",
-- "S 12"); with spaces and periods removed it is exactly the bill type followed by the number.
-- Procedural labels (JOURNAL, ADJOURN, MOTION, QUORUM) match no bill, and a bill that core.bill
-- does not hold leaves the roll call unlinked.
UPDATE core.roll_call r
SET bill_id = b.bill_id
FROM core.bill b
WHERE r.chamber = 'house' AND r.jurisdiction = 'us' AND r.bill_id IS NULL
  AND r.legislative_session = ANY(%(congresses)s::text[])
  AND b.jurisdiction = 'us'
  AND b.legislative_session = r.legislative_session
  AND b.bill_type IN ('hr', 'hres', 'hjres', 'hconres', 's', 'sres', 'sjres', 'sconres')
  AND upper(b.bill_type) || b.bill_number = translate(upper(r.legislative_number), ' .', '');
