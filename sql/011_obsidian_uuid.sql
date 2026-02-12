-- Add stable UUID column to obsidian.notes for rename-proof linking
-- UUID comes from frontmatter 'id' field in each Obsidian note
-- Run with: psql -h localhost -p 5433 -d connectingservices -f sql/011_obsidian_uuid.sql

BEGIN;

ALTER TABLE obsidian.notes ADD COLUMN IF NOT EXISTS uuid VARCHAR(36);

-- Unique where not null — allows notes without UUIDs during migration
CREATE UNIQUE INDEX IF NOT EXISTS idx_obsidian_notes_uuid
    ON obsidian.notes(uuid) WHERE uuid IS NOT NULL;

-- Backfill from existing frontmatter where possible
UPDATE obsidian.notes
SET uuid = frontmatter->>'id'
WHERE frontmatter IS NOT NULL
  AND frontmatter->>'id' IS NOT NULL
  AND uuid IS NULL;

COMMIT;

-- Verification
SELECT 'obsidian.notes' as table_name,
       COUNT(*) as total,
       COUNT(uuid) as with_uuid,
       COUNT(*) - COUNT(uuid) as without_uuid
FROM obsidian.notes;
