INSERT INTO core.bill_document (bill_id, document_id, relation)
VALUES (%(bill_id)s, %(document_id)s, %(relation)s)
ON CONFLICT (bill_id, document_id, relation) DO NOTHING;
