-- Grove Schema - Botanical Naming
-- Creates all tables in the 'todos' schema using plant-themed terminology
--
-- Hierarchy:
--   Groves (life areas) → Trunks (initiatives) → Branches (projects) → Buds (tasks)
--   Fruits = Key Results (measurable outcomes for trunks)
--   Seeds = Inbox items (buds with 'seed' status)
--
-- Tables: groves, trunks, fruits, branches, buds, bud_dependencies, habits, habit_log

-- Ensure the schema exists
CREATE SCHEMA IF NOT EXISTS todos;

-- Drop existing tables (in reverse dependency order) to allow clean recreation
DROP TABLE IF EXISTS todos.habit_log CASCADE;
DROP TABLE IF EXISTS todos.habits CASCADE;
DROP TABLE IF EXISTS todos.bud_dependencies CASCADE;
DROP TABLE IF EXISTS todos.task_dependencies CASCADE;
DROP TABLE IF EXISTS todos.subtasks CASCADE;
DROP TABLE IF EXISTS todos.buds CASCADE;
DROP TABLE IF EXISTS todos.tasks CASCADE;
DROP TABLE IF EXISTS todos.branches CASCADE;
DROP TABLE IF EXISTS todos.projects CASCADE;
DROP TABLE IF EXISTS todos.fruits CASCADE;
DROP TABLE IF EXISTS todos.key_results CASCADE;
DROP TABLE IF EXISTS todos.epics CASCADE;
DROP TABLE IF EXISTS todos.trunks CASCADE;
DROP TABLE IF EXISTS todos.initiatives CASCADE;
DROP TABLE IF EXISTS todos.groves CASCADE;
DROP TABLE IF EXISTS todos.areas CASCADE;

-- ============================================================================
-- GROVES (formerly Areas)
-- Broad life/work categories for organizing trunks
-- Examples: "Work", "Personal", "Health", "Learning"
-- ============================================================================
CREATE TABLE todos.groves (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    color VARCHAR(7),  -- hex color code like #FF5733
    icon VARCHAR(50),  -- emoji or icon identifier
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE todos.groves IS 'Life domains - the forests where your work grows';

-- ============================================================================
-- TRUNKS (formerly Initiatives)
-- Strategic goals or ongoing efforts, optionally tied to a grove
-- Can be nested (parent_id) for meta-trunks
-- ============================================================================
CREATE TABLE todos.trunks (
    id SERIAL PRIMARY KEY,
    grove_id INTEGER REFERENCES todos.groves(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES todos.trunks(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
    target_date DATE,
    labels TEXT[],
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE todos.trunks IS 'Strategic goals - the main stems that support your branches';

-- ============================================================================
-- FRUITS (formerly Key Results)
-- Measurable outcomes tied to trunks (OKR-style)
-- ============================================================================
CREATE TABLE todos.fruits (
    id SERIAL PRIMARY KEY,
    trunk_id INTEGER NOT NULL REFERENCES todos.trunks(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    target_value NUMERIC,
    current_value NUMERIC DEFAULT 0,
    unit VARCHAR(50),  -- e.g., "hours", "items", "%"
    target_date DATE,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'missed', 'abandoned')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE todos.fruits IS 'Measurable outcomes - the fruits that ripen as you make progress';

-- ============================================================================
-- BRANCHES (formerly Projects)
-- Containers for related buds, optionally tied to a trunk
-- ============================================================================
CREATE TABLE todos.branches (
    id SERIAL PRIMARY KEY,
    trunk_id INTEGER REFERENCES todos.trunks(id) ON DELETE SET NULL,
    grove_id INTEGER REFERENCES todos.groves(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
    target_date DATE,
    labels TEXT[],
    beads_repo VARCHAR(512),  -- path to linked beads repository
    done_when TEXT,  -- completion criteria
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE todos.branches IS 'Projects - branches that hold your buds';

-- ============================================================================
-- BUDS (formerly Tasks)
-- Core work items - the heart of the todo system
-- Status workflow: seed -> dormant -> budding -> bloomed/mulch
-- ============================================================================
CREATE TABLE todos.buds (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER REFERENCES todos.branches(id) ON DELETE SET NULL,
    trunk_id INTEGER REFERENCES todos.trunks(id) ON DELETE SET NULL,
    grove_id INTEGER REFERENCES todos.groves(id) ON DELETE SET NULL,

    -- Core fields
    title VARCHAR(500) NOT NULL,
    description TEXT,

    -- Status workflow: seed (inbox) -> dormant (clarified) -> budding (active) -> bloomed (done) / mulch (dropped)
    status VARCHAR(20) DEFAULT 'seed' CHECK (status IN ('seed', 'dormant', 'budding', 'waiting', 'bloomed', 'mulch')),

    -- Priority and effort
    priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
    story_points INTEGER,
    estimated_minutes INTEGER,

    -- Assignment and context
    assignee VARCHAR(100),
    context VARCHAR(100),  -- e.g., "@computer", "@phone", "@errands"
    energy_level VARCHAR(10) CHECK (energy_level IN ('high', 'medium', 'low')),  -- required energy

    -- Time tracking
    time_spent_minutes INTEGER DEFAULT 0,
    cost_cents INTEGER DEFAULT 0,

    -- Dates
    due_date DATE,
    scheduled_date DATE,  -- when to work on it
    defer_until DATE,     -- don't show until this date

    -- Metadata
    labels TEXT[],
    notes TEXT,

    -- Source tracking (for items created from Claude sessions)
    session_id UUID,
    source_message_id INTEGER,

    -- Beads integration
    beads_id VARCHAR(64),
    beads_synced_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    clarified_at TIMESTAMPTZ,  -- when moved from seed to dormant
    started_at TIMESTAMPTZ,    -- when moved to budding
    completed_at TIMESTAMPTZ   -- when bloomed
);

COMMENT ON TABLE todos.buds IS 'Work items - buds that bloom into completed work';

-- ============================================================================
-- BUD_DEPENDENCIES (formerly Task Dependencies)
-- Explicit dependency relationships between buds
-- ============================================================================
CREATE TABLE todos.bud_dependencies (
    id SERIAL PRIMARY KEY,
    bud_id INTEGER NOT NULL REFERENCES todos.buds(id) ON DELETE CASCADE,
    depends_on_id INTEGER NOT NULL REFERENCES todos.buds(id) ON DELETE CASCADE,
    dependency_type VARCHAR(20) DEFAULT 'blocks' CHECK (dependency_type IN ('blocks', 'related', 'subtask')),
    created_at TIMESTAMPTZ DEFAULT now(),

    -- Prevent self-dependencies and duplicates
    CONSTRAINT no_self_dependency CHECK (bud_id != depends_on_id),
    CONSTRAINT unique_dependency UNIQUE (bud_id, depends_on_id)
);

COMMENT ON TABLE todos.bud_dependencies IS 'Dependencies between buds - which buds must bloom first';

-- ============================================================================
-- HABITS
-- Recurring behaviors to track (unchanged naming)
-- ============================================================================
CREATE TABLE todos.habits (
    id SERIAL PRIMARY KEY,
    grove_id INTEGER REFERENCES todos.groves(id) ON DELETE SET NULL,

    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Frequency configuration
    frequency VARCHAR(20) DEFAULT 'daily' CHECK (frequency IN ('daily', 'weekly', 'monthly', 'custom')),
    frequency_config JSONB,  -- e.g., {"days": ["mon", "wed", "fri"]} or {"interval": 3}

    -- Tracking
    target_count INTEGER DEFAULT 1,  -- times per period
    streak_current INTEGER DEFAULT 0,
    streak_best INTEGER DEFAULT 0,

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Context
    context VARCHAR(100),
    preferred_time VARCHAR(20) CHECK (preferred_time IN ('morning', 'afternoon', 'evening', 'anytime')),

    -- Metadata
    labels TEXT[],

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE todos.habits IS 'Recurring behaviors to track with streak support';

-- ============================================================================
-- HABIT_LOG
-- History of habit completions (unchanged naming)
-- ============================================================================
CREATE TABLE todos.habit_log (
    id SERIAL PRIMARY KEY,
    habit_id INTEGER NOT NULL REFERENCES todos.habits(id) ON DELETE CASCADE,
    completed_at TIMESTAMPTZ DEFAULT now(),

    -- For habits with target_count > 1
    count INTEGER DEFAULT 1,

    -- Optional notes for this completion
    notes TEXT,

    -- Quality/rating of the habit completion (optional)
    quality INTEGER CHECK (quality >= 1 AND quality <= 5),

    -- For tracking related context
    session_id UUID,

    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE todos.habit_log IS 'History of habit completions';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Groves
CREATE INDEX idx_groves_is_active ON todos.groves(is_active);
CREATE INDEX idx_groves_sort_order ON todos.groves(sort_order);

-- Trunks
CREATE INDEX idx_trunks_grove_id ON todos.trunks(grove_id);
CREATE INDEX idx_trunks_parent_id ON todos.trunks(parent_id);
CREATE INDEX idx_trunks_status ON todos.trunks(status);
CREATE INDEX idx_trunks_priority ON todos.trunks(priority);

-- Fruits
CREATE INDEX idx_fruits_trunk_id ON todos.fruits(trunk_id);
CREATE INDEX idx_fruits_status ON todos.fruits(status);

-- Branches
CREATE INDEX idx_branches_trunk_id ON todos.branches(trunk_id);
CREATE INDEX idx_branches_grove_id ON todos.branches(grove_id);
CREATE INDEX idx_branches_status ON todos.branches(status);

-- Buds (critical for query performance)
CREATE INDEX idx_buds_branch_id ON todos.buds(branch_id);
CREATE INDEX idx_buds_trunk_id ON todos.buds(trunk_id);
CREATE INDEX idx_buds_grove_id ON todos.buds(grove_id);
CREATE INDEX idx_buds_status ON todos.buds(status);
CREATE INDEX idx_buds_priority ON todos.buds(priority);
CREATE INDEX idx_buds_due_date ON todos.buds(due_date);
CREATE INDEX idx_buds_scheduled_date ON todos.buds(scheduled_date);
CREATE INDEX idx_buds_defer_until ON todos.buds(defer_until);
CREATE INDEX idx_buds_context ON todos.buds(context);
CREATE INDEX idx_buds_created_at ON todos.buds(created_at DESC);
CREATE INDEX idx_buds_assignee ON todos.buds(assignee);
CREATE INDEX idx_buds_beads_id ON todos.buds(beads_id);

-- Composite indexes for common query patterns
CREATE INDEX idx_buds_seeds ON todos.buds(status, created_at DESC) WHERE status = 'seed';
CREATE INDEX idx_buds_budding ON todos.buds(priority, due_date) WHERE status = 'budding';
CREATE INDEX idx_buds_today ON todos.buds(scheduled_date, priority) WHERE status IN ('budding', 'dormant');

-- Bud Dependencies
CREATE INDEX idx_bud_deps_bud_id ON todos.bud_dependencies(bud_id);
CREATE INDEX idx_bud_deps_depends_on_id ON todos.bud_dependencies(depends_on_id);
CREATE INDEX idx_bud_deps_type ON todos.bud_dependencies(dependency_type);

-- Habits
CREATE INDEX idx_habits_grove_id ON todos.habits(grove_id);
CREATE INDEX idx_habits_is_active ON todos.habits(is_active);
CREATE INDEX idx_habits_frequency ON todos.habits(frequency);

-- Habit Log
CREATE INDEX idx_habit_log_habit_id ON todos.habit_log(habit_id);
CREATE INDEX idx_habit_log_completed_at ON todos.habit_log(completed_at DESC);
CREATE INDEX idx_habit_log_habit_date ON todos.habit_log(habit_id, completed_at DESC);

-- ============================================================================
-- TRIGGERS for updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION todos.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER groves_updated_at
    BEFORE UPDATE ON todos.groves
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER trunks_updated_at
    BEFORE UPDATE ON todos.trunks
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER fruits_updated_at
    BEFORE UPDATE ON todos.fruits
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER branches_updated_at
    BEFORE UPDATE ON todos.branches
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER buds_updated_at
    BEFORE UPDATE ON todos.buds
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER habits_updated_at
    BEFORE UPDATE ON todos.habits
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();
