-- Repoint one table's person_id. {table} is chosen from a fixed list in code, never input.
UPDATE {table} SET person_id = %(survivor)s WHERE person_id = %(duplicate)s
