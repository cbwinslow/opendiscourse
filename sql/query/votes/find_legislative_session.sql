-- The session row of one Congress, if the warehouse has it (billstatus creates them).
SELECT legislative_session_id
FROM core.legislative_session
WHERE jurisdiction_id = %(jurisdiction_id)s AND identifier = %(identifier)s;
