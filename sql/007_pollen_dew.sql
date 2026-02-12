-- Pollen and Dew: AI-generated ideas and ambient data signals
-- Run with: psql -d connectingservices -f sql/007_pollen_dew.sql

BEGIN;

-- ============================================================================
-- POLLEN: AI-generated ideas and external suggestions
-- ============================================================================
CREATE TABLE IF NOT EXISTS todos.pollen (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    source VARCHAR(100) NOT NULL,
    source_meta JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    confidence FLOAT,
    seed_id INTEGER REFERENCES todos.buds(id),
    reject_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    CONSTRAINT valid_pollen_status CHECK (status IN ('pending', 'seeded', 'rejected'))
);

CREATE INDEX IF NOT EXISTS idx_pollen_status ON todos.pollen(status);
CREATE INDEX IF NOT EXISTS idx_pollen_source ON todos.pollen(source);
CREATE INDEX IF NOT EXISTS idx_pollen_created ON todos.pollen(created_at DESC);

COMMENT ON TABLE todos.pollen IS 'AI-generated ideas and external suggestions - arrives from other systems';
COMMENT ON COLUMN todos.pollen.status IS 'Status lifecycle: pending -> seeded/rejected';
COMMENT ON COLUMN todos.pollen.seed_id IS 'If status=seeded, the bud this pollen became';
COMMENT ON COLUMN todos.pollen.source IS 'Where this pollen came from (e.g., claude, gemini, manual)';
COMMENT ON COLUMN todos.pollen.confidence IS 'AI confidence score (0.0-1.0) if applicable';

-- ============================================================================
-- DEW: Ambient data signals
-- ============================================================================
CREATE TABLE IF NOT EXISTS todos.dew (
    id SERIAL PRIMARY KEY,
    content TEXT,
    payload JSONB,
    source VARCHAR(100) NOT NULL,
    source_meta JSONB,
    status VARCHAR(20) DEFAULT 'fresh',
    item_type VARCHAR(10),
    item_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    absorbed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    CONSTRAINT valid_dew_status CHECK (status IN ('fresh', 'absorbed', 'evaporated')),
    CONSTRAINT valid_dew_item_type CHECK (item_type IS NULL OR item_type IN ('g', 't', 's', 'b', 'f'))
);

CREATE INDEX IF NOT EXISTS idx_dew_status ON todos.dew(status);
CREATE INDEX IF NOT EXISTS idx_dew_source ON todos.dew(source);
CREATE INDEX IF NOT EXISTS idx_dew_item ON todos.dew(item_type, item_id) WHERE item_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dew_expires ON todos.dew(expires_at) WHERE status = 'fresh';
CREATE INDEX IF NOT EXISTS idx_dew_created ON todos.dew(created_at DESC);

COMMENT ON TABLE todos.dew IS 'Ambient data signals - context enrichment for existing items';
COMMENT ON COLUMN todos.dew.status IS 'Status lifecycle: fresh -> absorbed/evaporated';
COMMENT ON COLUMN todos.dew.item_type IS 'Type of item this dew is attached to (g/t/s/b/f)';
COMMENT ON COLUMN todos.dew.item_id IS 'ID of item this dew is attached to';
COMMENT ON COLUMN todos.dew.source IS 'Where this dew came from (e.g., calendar, email, webhook)';
COMMENT ON COLUMN todos.dew.expires_at IS 'When this dew becomes stale and should evaporate';

-- ============================================================================
-- UPDATE ACTIVITY_LOG CONSTRAINT for new event types
-- ============================================================================
ALTER TABLE todos.activity_log DROP CONSTRAINT IF EXISTS activity_log_event_type_check;
ALTER TABLE todos.activity_log ADD CONSTRAINT activity_log_event_type_check CHECK (
    event_type IN (
        'created', 'checked', 'log', 'ref_added', 'status_changed',
        'bead_synced', 'tidy_scan', 'grafted', 'split',
        'dew_absorbed', 'pollen_seeded'
    )
);

COMMIT;

-- ============================================================================
-- VERIFICATION
-- ============================================================================
SELECT 'pollen' as table_name, COUNT(*) as rows FROM todos.pollen
UNION ALL
SELECT 'dew', COUNT(*) FROM todos.dew;
