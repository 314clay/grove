-- Rename branches to stems (avoid git terminology collision)
-- Run with: psql -d connectingservices -f sql/006_rename_branch_to_stem.sql
--
-- Strategy: Create new table, migrate data, update FKs, keep old table for safety

BEGIN;

-- ============================================================================
-- 1. CREATE STEMS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS todos.stems (
    id SERIAL PRIMARY KEY,
    trunk_id INTEGER REFERENCES todos.trunks(id) ON DELETE SET NULL,
    grove_id INTEGER REFERENCES todos.groves(id) ON DELETE SET NULL,
    parent_stem_id INTEGER REFERENCES todos.stems(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    priority VARCHAR(10) DEFAULT 'medium'
        CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
    target_date DATE,
    labels TEXT[],
    done_when TEXT,
    beads_repo VARCHAR(512),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    last_checked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_stems_trunk_id ON todos.stems(trunk_id);
CREATE INDEX IF NOT EXISTS idx_stems_grove_id ON todos.stems(grove_id);
CREATE INDEX IF NOT EXISTS idx_stems_status ON todos.stems(status);
CREATE INDEX IF NOT EXISTS idx_stems_parent ON todos.stems(parent_stem_id) WHERE parent_stem_id IS NOT NULL;

-- Create the updated_at trigger for stems
DROP TRIGGER IF EXISTS stems_updated_at ON todos.stems;
CREATE TRIGGER stems_updated_at
    BEFORE UPDATE ON todos.stems
    FOR EACH ROW
    EXECUTE FUNCTION todos.update_updated_at();

COMMENT ON TABLE todos.stems IS 'Projects - stems that hold your buds (renamed from branches)';

-- ============================================================================
-- 2. MIGRATE DATA FROM BRANCHES TO STEMS
-- ============================================================================
-- First pass: insert all branches (without parent_stem_id to avoid FK issues)
INSERT INTO todos.stems (id, trunk_id, grove_id, title, description, status, priority, target_date, labels, done_when, beads_repo, created_at, updated_at, last_checked_at)
SELECT id, trunk_id, grove_id, title, description, status, priority, target_date, labels, done_when, beads_repo, created_at, updated_at, last_checked_at
FROM todos.branches
ON CONFLICT (id) DO NOTHING;

-- Reset sequence to max id
SELECT setval('todos.stems_id_seq', COALESCE((SELECT MAX(id) FROM todos.stems), 0) + 1, false);

-- Second pass: update parent_stem_id (now that all stems exist)
UPDATE todos.stems s
SET parent_stem_id = b.parent_branch_id
FROM todos.branches b
WHERE s.id = b.id AND b.parent_branch_id IS NOT NULL;

-- ============================================================================
-- 3. ADD STEM_ID TO BUDS (alongside branch_id temporarily)
-- ============================================================================
ALTER TABLE todos.buds ADD COLUMN IF NOT EXISTS stem_id INTEGER REFERENCES todos.stems(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_buds_stem_id ON todos.buds(stem_id);

-- Migrate branch_id to stem_id
UPDATE todos.buds SET stem_id = branch_id WHERE branch_id IS NOT NULL;

-- ============================================================================
-- 4. ADD STEM_ID TO BEAD_LINKS (alongside branch_id temporarily)
-- ============================================================================
ALTER TABLE todos.bead_links ADD COLUMN IF NOT EXISTS stem_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_bead_links_stem_id ON todos.bead_links(stem_id) WHERE stem_id IS NOT NULL;

-- Migrate branch_id to stem_id
UPDATE todos.bead_links SET stem_id = branch_id WHERE branch_id IS NOT NULL;

-- ============================================================================
-- 5. UPDATE ACTIVITY_LOG ITEM_TYPE CHECK
-- ============================================================================
ALTER TABLE todos.activity_log DROP CONSTRAINT IF EXISTS activity_log_item_type_check;
ALTER TABLE todos.activity_log ADD CONSTRAINT activity_log_item_type_check
    CHECK (item_type IN ('grove', 'trunk', 'branch', 'stem', 'bud'));

-- Migrate existing 'branch' entries to 'stem'
UPDATE todos.activity_log SET item_type = 'stem' WHERE item_type = 'branch';

-- ============================================================================
-- 6. UPDATE REFS ITEM_TYPE CHECK
-- ============================================================================
ALTER TABLE todos.refs DROP CONSTRAINT IF EXISTS refs_item_type_check;
ALTER TABLE todos.refs ADD CONSTRAINT refs_item_type_check
    CHECK (item_type IN ('grove', 'trunk', 'branch', 'stem', 'bud'));

-- Migrate existing 'branch' entries to 'stem'
UPDATE todos.refs SET item_type = 'stem' WHERE item_type = 'branch';

-- ============================================================================
-- 7. UPDATE ROOT_LINKS ITEM_TYPE CHECK
-- ============================================================================
ALTER TABLE todos.root_links DROP CONSTRAINT IF EXISTS root_links_item_type_check;
ALTER TABLE todos.root_links ADD CONSTRAINT root_links_item_type_check
    CHECK (item_type IN ('grove', 'trunk', 'branch', 'stem', 'bud'));

-- Migrate existing 'branch' entries to 'stem'
UPDATE todos.root_links SET item_type = 'stem' WHERE item_type = 'branch';

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT 'stems' as table_name, COUNT(*) as rows FROM todos.stems
UNION ALL
SELECT 'branches (old)', COUNT(*) FROM todos.branches
UNION ALL
SELECT 'buds with stem_id', COUNT(*) FROM todos.buds WHERE stem_id IS NOT NULL
UNION ALL
SELECT 'bead_links with stem_id', COUNT(*) FROM todos.bead_links WHERE stem_id IS NOT NULL;
