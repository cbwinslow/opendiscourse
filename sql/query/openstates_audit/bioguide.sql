SELECT count(*) AS person_count,
       count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM {identifiers} i
          WHERE i.person_id=p.id AND lower(i.scheme)='bioguide' AND i.identifier IS NOT NULL AND i.identifier<>'')) AS missing_bioguide_count,
       (SELECT count(*) FROM (SELECT identifier FROM {identifiers}
          WHERE lower(scheme)='bioguide' AND identifier IS NOT NULL AND identifier<>''
          GROUP BY identifier HAVING count(DISTINCT person_id)>1) duplicates) AS duplicate_bioguide_count,
       (SELECT count(*) FROM (SELECT name FROM {people}
          GROUP BY name HAVING count(DISTINCT id)>1) collisions) AS name_collision_groups
FROM {people} p;
