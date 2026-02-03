-- Create bead_links table for linking beads to branches and buds
-- Run with: psql -d connectingservices -f sql/002_bead_links.sql

BEGIN;

-- ============================================================================
-- BEAD_LINKS
-- Junction table linking external beads (from beads repos) to branches or buds
-- Enables tracking which beads are being worked on in which projects/tasks
-- ============================================================================
CREATE TABLE todos.bead_links (
    id SERIAL PRIMARY KEY,
    bead_id VARCHAR(64) NOT NULL,           -- The bead ID from the beads repo
    bead_repo VARCHAR(512) NOT NULL,        -- Path to the beads repo this came from
    bud_id INTEGER REFERENCES todos.buds(id) ON DELETE CASCADE,
    branch_id INTEGER REFERENCES todos.branches(id) ON DELETE CASCADE,
    link_type VARCHAR(20) DEFAULT 'tracks', -- 'tracks', 'implements', 'blocks'
    created_at TIMESTAMPTZ DEFAULT now(),

    -- Must link to either a bud or branch (not both, not neither)
    CONSTRAINT bead_link_target CHECK (
        (bud_id IS NOT NULL AND branch_id IS NULL) OR
        (bud_id IS NULL AND branch_id IS NOT NULL)
    ),
    -- Prevent duplicate links
    CONSTRAINT unique_bead_bud UNIQUE (bead_id, bud_id),
    CONSTRAINT unique_bead_branch UNIQUE (bead_id, branch_id)
);

COMMENT ON TABLE todos.bead_links IS 'Links external beads (AI-native issues) to branches or buds for tracking implementation';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Primary lookup by bead_id (find all links for a specific bead)
CREATE INDEX idx_bead_links_bead_id ON todos.bead_links(bead_id);

-- Lookup by bud_id (find all beads linked to a specific bud)
CREATE INDEX idx_bead_links_bud_id ON todos.bead_links(bud_id) WHERE bud_id IS NOT NULL;

-- Lookup by branch_id (find all beads linked to a specific branch)
CREATE INDEX idx_bead_links_branch_id ON todos.bead_links(branch_id) WHERE branch_id IS NOT NULL;

-- Lookup by bead_repo (find all links from a specific beads repository)
CREATE INDEX idx_bead_links_bead_repo ON todos.bead_links(bead_repo);

COMMIT;

-- Verification query
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'todos'
  AND table_name = 'bead_links'
ORDER BY ordinal_position;
