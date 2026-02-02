-- Add beads integration fields to tasks table
-- Run with: psql -d connectingservices -f sql/001_add_beads_fields.sql

BEGIN;

-- Add beads_id column for linking tasks to beads issues
ALTER TABLE todos.tasks
ADD COLUMN IF NOT EXISTS beads_id VARCHAR(64);

-- Add beads_synced_at column for tracking last sync time
ALTER TABLE todos.tasks
ADD COLUMN IF NOT EXISTS beads_synced_at TIMESTAMP;

-- Create index for efficient lookups by beads_id
CREATE INDEX IF NOT EXISTS idx_tasks_beads_id
ON todos.tasks(beads_id) WHERE beads_id IS NOT NULL;

COMMIT;

-- Verification query
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'todos'
  AND table_name = 'tasks'
  AND column_name IN ('beads_id', 'beads_synced_at');
