-- Upgrade databases initialized while 005 used the earlier generic column name.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'core' AND table_name = 'embedding' AND column_name = 'values'
  ) THEN
    ALTER TABLE core.embedding RENAME COLUMN "values" TO vector_values;
  END IF;
END $$;
