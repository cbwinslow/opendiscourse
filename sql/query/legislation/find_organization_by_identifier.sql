SELECT organization_id FROM core.organization_identifier
WHERE namespace = %(namespace)s AND external_id = %(external_id)s;
