SELECT scheme AS namespace, count(*) AS identifier_count,
       count(DISTINCT person_id) AS person_count,
       count(*) FILTER (WHERE identifier IS NULL OR identifier = '') AS missing_count,
       count(*) - count(DISTINCT (person_id, identifier)) AS duplicate_assertions
FROM {identifiers} GROUP BY scheme ORDER BY scheme;
