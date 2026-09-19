SELECT organization_id, organization_type
FROM core.organization
WHERE jurisdiction_geoid = 'us' AND organization_type IN ('lower', 'upper')
