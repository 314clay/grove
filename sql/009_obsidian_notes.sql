-- Obsidian vault notes: synced from local vault for dew browsing
-- Run with: psql -h localhost -p 5433 -d connectingservices -f sql/009_obsidian_notes.sql

BEGIN;

CREATE SCHEMA IF NOT EXISTS obsidian;

CREATE TABLE IF NOT EXISTS obsidian.notes (
    id SERIAL PRIMARY KEY,
    path VARCHAR(1024) NOT NULL UNIQUE,   -- relative to vault root
    title VARCHAR(500) NOT NULL,          -- filename without .md
    content TEXT,                         -- body (frontmatter stripped)
    frontmatter JSONB,                    -- parsed YAML frontmatter
    tags TEXT[],                          -- extracted from frontmatter
    folder VARCHAR(500),                  -- parent dir or NULL for root
    modified_at TIMESTAMPTZ,              -- file mtime
    content_hash VARCHAR(32),             -- MD5 for change detection
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_obsidian_notes_folder ON obsidian.notes(folder);
CREATE INDEX IF NOT EXISTS idx_obsidian_notes_modified ON obsidian.notes(modified_at DESC);
CREATE INDEX IF NOT EXISTS idx_obsidian_notes_tags ON obsidian.notes USING gin(tags);

COMMIT;

-- Verification
SELECT 'obsidian.notes' as table_name, COUNT(*) as rows FROM obsidian.notes;
