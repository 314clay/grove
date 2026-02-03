-- Roots: Source materials that feed ideas (quotes, transcripts, session context)
-- Run with: psql -d connectingservices -f sql/004_roots.sql

BEGIN;

-- ============================================================================
-- ROOTS
-- Source materials that can be linked to multiple Grove items
-- ============================================================================
CREATE TABLE IF NOT EXISTS todos.roots (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    source_type VARCHAR(20) DEFAULT 'quote'
        CHECK (source_type IN ('quote', 'transcript', 'session', 'note')),
    label TEXT,
    session_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_roots_session ON todos.roots(session_id) WHERE session_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_roots_type ON todos.roots(source_type);

COMMENT ON TABLE todos.roots IS 'Source materials (quotes, transcripts) that feed ideas';

-- ============================================================================
-- ROOT_LINKS
-- Junction table linking roots to Grove items (many-to-many)
-- ============================================================================
CREATE TABLE IF NOT EXISTS todos.root_links (
    id SERIAL PRIMARY KEY,
    root_id INTEGER NOT NULL REFERENCES todos.roots(id) ON DELETE CASCADE,
    item_type VARCHAR(20) NOT NULL
        CHECK (item_type IN ('grove', 'trunk', 'branch', 'bud')),
    item_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(root_id, item_type, item_id)
);

CREATE INDEX IF NOT EXISTS idx_root_links_root ON todos.root_links(root_id);
CREATE INDEX IF NOT EXISTS idx_root_links_item ON todos.root_links(item_type, item_id);

COMMENT ON TABLE todos.root_links IS 'Links roots to buds, branches, trunks, or groves';

COMMIT;

-- Verification
SELECT 'roots' as table_name, COUNT(*) as rows FROM todos.roots
UNION ALL
SELECT 'root_links', COUNT(*) FROM todos.root_links;
