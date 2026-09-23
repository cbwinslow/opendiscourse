-- Remove party rows before the new file is inserted, in the same transaction.
DELETE FROM core.voteview_party
RETURNING 1
