-- Links whose boundary is not the vintage their product requires (or is the wrong family).
SELECT link.division_boundary_id, division.ocd_division_id, geography.geography_type, boundary.boundary_vintage
FROM core.division_boundary AS link
JOIN core.division AS division USING (division_id)
JOIN core.geography_boundary AS boundary USING (boundary_id)
JOIN core.geography AS geography USING (geography_id)
WHERE (link.congress = %(congress)s
       AND (boundary.boundary_vintage <> %(vintage)s OR geography.geography_type <> 'congressional_district'))
   OR (link.legislative_year = %(legislative_year)s
       AND (boundary.boundary_vintage <> %(vintage)s OR geography.geography_type NOT IN ('sldu', 'sldl')))
ORDER BY 2;
