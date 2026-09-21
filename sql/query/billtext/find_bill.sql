-- Join a BILLS version to an existing BILLSTATUS bill. Never insert from text alone.
SELECT bill_id
FROM core.bill
WHERE jurisdiction = %(jurisdiction)s
  AND legislative_session = %(legislative_session)s
  AND bill_type = %(bill_type)s
  AND bill_number = %(bill_number)s;
