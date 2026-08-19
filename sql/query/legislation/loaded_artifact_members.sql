SELECT metadata ->> 'member_name' AS source_member
FROM core.bill_identifier
WHERE namespace = 'govinfo.package'
  AND source_artifact_id = %(artifact_id)s
  AND metadata ? 'member_name';
