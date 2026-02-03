-- Branch nesting and tidy activity event types
-- Run with: psql -d connectingservices -f sql/005_branch_nesting.sql

BEGIN;

-- ============================================================================
-- BRANCH NESTING
-- Adds parent_branch_id to allow sub-branches (like trunks already support)
-- ============================================================================
ALTER TABLE todos.branches
ADD COLUMN IF NOT EXISTS parent_branch_id INTEGER REFERENCES todos.branches(id);

CREATE INDEX IF NOT EXISTS idx_branches_parent ON todos.branches(parent_branch_id)
WHERE parent_branch_id IS NOT NULL;

COMMENT ON COLUMN todos.branches.parent_branch_id IS 'Parent branch for sub-branch hierarchies';

-- ============================================================================
-- TIDY ACTIVITY EVENT TYPES
-- Update the activity_log event_type check constraint to include tidy events
-- ============================================================================

-- Drop existing constraint
ALTER TABLE todos.activity_log
DROP CONSTRAINT IF EXISTS activity_log_event_type_check;

-- Add updated constraint with new event types
ALTER TABLE todos.activity_log
ADD CONSTRAINT activity_log_event_type_check
CHECK (event_type IN (
    'created',
    'checked',
    'log',
    'ref_added',
    'status_changed',
    'bead_synced',
    'tidy_scan',
    'grafted',
    'split'
));

-- ============================================================================
-- TIDY CONFIG TABLE
-- Stores user preferences for tidy thresholds
-- ============================================================================
CREATE TABLE IF NOT EXISTS todos.tidy_config (
    key VARCHAR(50) PRIMARY KEY,
    value INTEGER NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Insert default thresholds
INSERT INTO todos.tidy_config (key, value) VALUES
    ('branches_per_trunk', 10),
    ('buds_per_branch', 10),
    ('fruits_per_trunk', 10)
ON CONFLICT (key) DO NOTHING;

COMMENT ON TABLE todos.tidy_config IS 'Configuration for gv tidy thresholds';

COMMIT;

-- Verification
SELECT 'branches.parent_branch_id' as check_item,
       CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'todos'
           AND table_name = 'branches'
           AND column_name = 'parent_branch_id'
       ) THEN 'OK' ELSE 'MISSING' END as status
UNION ALL
SELECT 'tidy_config table',
       CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.tables
           WHERE table_schema = 'todos'
           AND table_name = 'tidy_config'
       ) THEN 'OK' ELSE 'MISSING' END;
