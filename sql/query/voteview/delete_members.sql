-- Remove member rows before the new file is inserted, in the same transaction.
DELETE FROM core.voteview_member
RETURNING 1
