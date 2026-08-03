SELECT regexp_replace(identifier, '^.*\s+([0-9]+)$', '\1') AS bill_number
FROM leg.bill
WHERE jurisdiction_id = 'ocd-jurisdiction/country:us/government'
  AND legislative_session_identifier = %(congress)s
  AND lower(regexp_replace(identifier, '\s+[0-9]+$', '')) = %(bill_type)s;
