-- Remove roll-call rows before the new file is inserted, in the same transaction.
DELETE FROM core.voteview_roll_call
RETURNING 1
