-- Activity log and refs tables for AI context tracking
-- Run with: psql -d connectingservices -f sql/003_activity_refs.sql

BEGIN;

-- ============================================================================
-- ACTIVITY_LOG
-- Append-only log of events for temporal tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS todos.activity_log (
    id SERIAL PRIMARY KEY,
    item_type VARCHAR(20) NOT NULL CHECK (item_type IN ('grove', 'trunk', 'branch', 'bud')),
    item_id INTEGER NOT NULL,
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN ('created', 'checked', 'log', 'ref_added', 'status_changed', 'bead_synced')),
    content TEXT,
    session_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_activity_log_item ON todos.activity_log(item_type, item_id, created_at DESC);
CREATE INDEX idx_activity_log_session ON todos.activity_log(session_id) WHERE session_id IS NOT NULL;

COMMENT ON TABLE todos.activity_log IS 'Append-only event log for AI context tracking';

-- ============================================================================
-- REFS
-- Structured references to external resources (notes, files, URLs)
-- Note: beads are tracked in bead_links table, not here
-- ============================================================================
CREATE TABLE IF NOT EXISTS todos.refs (
    id SERIAL PRIMARY KEY,
    item_type VARCHAR(20) NOT NULL CHECK (item_type IN ('grove', 'trunk', 'branch', 'bud')),
    item_id INTEGER NOT NULL,
    ref_type VARCHAR(20) NOT NULL CHECK (ref_type IN ('note', 'file', 'url')),
    value TEXT NOT NULL,
    label TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_refs_item ON todos.refs(item_type, item_id);

COMMENT ON TABLE todos.refs IS 'Structured references to notes, files, and URLs';

-- ============================================================================
-- ADD last_checked_at TO EXISTING TABLES
-- Tracks when AI last reviewed this item via gv context
-- ============================================================================
ALTER TABLE todos.groves ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;
ALTER TABLE todos.trunks ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;
ALTER TABLE todos.branches ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;
ALTER TABLE todos.buds ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;

COMMIT;

-- Verification
SELECT 'activity_log' as table_name, count(*) as columns
FROM information_schema.columns
WHERE table_schema = 'todos' AND table_name = 'activity_log'
UNION ALL
SELECT 'refs', count(*)
FROM information_schema.columns
WHERE table_schema = 'todos' AND table_name = 'refs';
