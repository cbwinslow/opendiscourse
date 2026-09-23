-- One printed Voteview name per linked person and Congress. Vintage is the Congress
-- number zero-padded to four digits so it sorts as text and passes the vintage check.
SELECT person_id::text AS person_id,
       lpad(congress::text, 4, '0') AS source_vintage,
       bioname
FROM core.voteview_member
WHERE person_id IS NOT NULL
