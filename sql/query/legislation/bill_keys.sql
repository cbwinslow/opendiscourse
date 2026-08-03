SELECT bill_type, bill_number
FROM core.bill
WHERE jurisdiction = 'us'
  AND legislative_session = %(congress)s
  AND bill_type = %(bill_type)s;
