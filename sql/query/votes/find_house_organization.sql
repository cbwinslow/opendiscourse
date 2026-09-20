-- The House's organization, by the OpenStates OCD identifier the existing roll calls already use.
SELECT organization_id
FROM core.organization_identifier
WHERE namespace = 'ocd' AND external_id = %(ocd_id)s;
