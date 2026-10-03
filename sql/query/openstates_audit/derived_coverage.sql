SELECT {dimensions}, count(*)::bigint AS row_count,
       count(*) FILTER (WHERE {unresolved_link})::bigint AS unresolved_link_count,
       {unresolved_dimensions}
FROM {relation} AS r0
{joins}
GROUP BY {groups}
ORDER BY {groups};
