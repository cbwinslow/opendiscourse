SELECT discovery_id, dataset_id, state, cursor, statistics, error_message
FROM catalog.discovery
WHERE discovery_id = %(discovery_id)s;
