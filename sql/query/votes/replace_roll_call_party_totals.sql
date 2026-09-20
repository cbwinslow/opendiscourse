-- Totals by party are replaced as a set: a refreshed file may drop or rename a party.
DELETE FROM core.roll_call_party_total WHERE roll_call_id = %(roll_call_id)s;
