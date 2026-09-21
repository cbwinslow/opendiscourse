-- Loaded BILLS version files per Congress (for coverage).
SELECT congress, count(*) AS n
FROM core.bill_text_source_record
GROUP BY 1;
