-- Todo System Schema
-- Creates all tables in the 'todos' schema
-- Tables: areas, initiatives, key_results, projects, tasks, task_dependencies, habits, habit_log

-- Ensure the schema exists
CREATE SCHEMA IF NOT EXISTS todos;

-- Drop existing tables (in reverse dependency order) to allow clean recreation
DROP TABLE IF EXISTS todos.habit_log CASCADE;
DROP TABLE IF EXISTS todos.habits CASCADE;
DROP TABLE IF EXISTS todos.task_dependencies CASCADE;
DROP TABLE IF EXISTS todos.subtasks CASCADE;
DROP TABLE IF EXISTS todos.tasks CASCADE;
DROP TABLE IF EXISTS todos.projects CASCADE;
DROP TABLE IF EXISTS todos.key_results CASCADE;
DROP TABLE IF EXISTS todos.epics CASCADE;
DROP TABLE IF EXISTS todos.initiatives CASCADE;
DROP TABLE IF EXISTS todos.areas CASCADE;

-- ============================================================================
-- AREAS
-- Broad life/work categories for organizing initiatives
-- Examples: "Work", "Personal", "Health", "Learning"
-- ============================================================================
CREATE TABLE todos.areas (
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

COMMENT ON TABLE todos.areas IS 'Broad life/work categories for organizing initiatives';

-- ============================================================================
-- INITIATIVES
-- Strategic goals or ongoing efforts, optionally tied to an area
-- Can be nested (parent_id) for meta-initiatives
-- ============================================================================
CREATE TABLE todos.initiatives (
    id SERIAL PRIMARY KEY,
    area_id INTEGER REFERENCES todos.areas(id) ON DELETE SET NULL,
    parent_id INTEGER REFERENCES todos.initiatives(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
    target_date DATE,
    labels TEXT[],
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE todos.initiatives IS 'Strategic goals or ongoing efforts, supports nesting via parent_id';

-- ============================================================================
-- KEY_RESULTS
-- Measurable outcomes tied to initiatives (OKR-style)
-- ============================================================================
CREATE TABLE todos.key_results (
    id SERIAL PRIMARY KEY,
    initiative_id INTEGER NOT NULL REFERENCES todos.initiatives(id) ON DELETE CASCADE,
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

COMMENT ON TABLE todos.key_results IS 'Measurable outcomes tied to initiatives (OKR-style tracking)';

-- ============================================================================
-- PROJECTS
-- Containers for related tasks, optionally tied to an initiative
-- ============================================================================
CREATE TABLE todos.projects (
    id SERIAL PRIMARY KEY,
    initiative_id INTEGER REFERENCES todos.initiatives(id) ON DELETE SET NULL,
    area_id INTEGER REFERENCES todos.areas(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'archived')),
    priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
    target_date DATE,
    labels TEXT[],
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE todos.projects IS 'Containers for related tasks, optionally tied to initiatives';

-- ============================================================================
-- TASKS
-- Core work items - the heart of the todo system
-- ============================================================================
CREATE TABLE todos.tasks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES todos.projects(id) ON DELETE SET NULL,
    initiative_id INTEGER REFERENCES todos.initiatives(id) ON DELETE SET NULL,
    area_id INTEGER REFERENCES todos.areas(id) ON DELETE SET NULL,

    -- Core fields
    title VARCHAR(500) NOT NULL,
    description TEXT,

    -- Status workflow: inbox -> clarified -> active -> done/dropped
    status VARCHAR(20) DEFAULT 'inbox' CHECK (status IN ('inbox', 'clarified', 'active', 'waiting', 'done', 'dropped')),

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

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    clarified_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

COMMENT ON TABLE todos.tasks IS 'Core work items with inbox workflow support';

-- ============================================================================
-- TASK_DEPENDENCIES
-- Explicit dependency relationships between tasks
-- ============================================================================
CREATE TABLE todos.task_dependencies (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES todos.tasks(id) ON DELETE CASCADE,
    depends_on_id INTEGER NOT NULL REFERENCES todos.tasks(id) ON DELETE CASCADE,
    dependency_type VARCHAR(20) DEFAULT 'blocks' CHECK (dependency_type IN ('blocks', 'related', 'subtask')),
    created_at TIMESTAMPTZ DEFAULT now(),

    -- Prevent self-dependencies and duplicates
    CONSTRAINT no_self_dependency CHECK (task_id != depends_on_id),
    CONSTRAINT unique_dependency UNIQUE (task_id, depends_on_id)
);

COMMENT ON TABLE todos.task_dependencies IS 'Explicit dependency relationships between tasks';

-- ============================================================================
-- HABITS
-- Recurring behaviors to track
-- ============================================================================
CREATE TABLE todos.habits (
    id SERIAL PRIMARY KEY,
    area_id INTEGER REFERENCES todos.areas(id) ON DELETE SET NULL,

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
-- History of habit completions
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

-- Areas
CREATE INDEX idx_areas_is_active ON todos.areas(is_active);
CREATE INDEX idx_areas_sort_order ON todos.areas(sort_order);

-- Initiatives
CREATE INDEX idx_initiatives_area_id ON todos.initiatives(area_id);
CREATE INDEX idx_initiatives_parent_id ON todos.initiatives(parent_id);
CREATE INDEX idx_initiatives_status ON todos.initiatives(status);
CREATE INDEX idx_initiatives_priority ON todos.initiatives(priority);

-- Key Results
CREATE INDEX idx_key_results_initiative_id ON todos.key_results(initiative_id);
CREATE INDEX idx_key_results_status ON todos.key_results(status);

-- Projects
CREATE INDEX idx_projects_initiative_id ON todos.projects(initiative_id);
CREATE INDEX idx_projects_area_id ON todos.projects(area_id);
CREATE INDEX idx_projects_status ON todos.projects(status);

-- Tasks (critical for query performance)
CREATE INDEX idx_tasks_project_id ON todos.tasks(project_id);
CREATE INDEX idx_tasks_initiative_id ON todos.tasks(initiative_id);
CREATE INDEX idx_tasks_area_id ON todos.tasks(area_id);
CREATE INDEX idx_tasks_status ON todos.tasks(status);
CREATE INDEX idx_tasks_priority ON todos.tasks(priority);
CREATE INDEX idx_tasks_due_date ON todos.tasks(due_date);
CREATE INDEX idx_tasks_scheduled_date ON todos.tasks(scheduled_date);
CREATE INDEX idx_tasks_defer_until ON todos.tasks(defer_until);
CREATE INDEX idx_tasks_context ON todos.tasks(context);
CREATE INDEX idx_tasks_created_at ON todos.tasks(created_at DESC);
CREATE INDEX idx_tasks_assignee ON todos.tasks(assignee);

-- Composite indexes for common query patterns
CREATE INDEX idx_tasks_inbox ON todos.tasks(status, created_at DESC) WHERE status = 'inbox';
CREATE INDEX idx_tasks_active ON todos.tasks(priority, due_date) WHERE status = 'active';
CREATE INDEX idx_tasks_today ON todos.tasks(scheduled_date, priority) WHERE status IN ('active', 'clarified');

-- Task Dependencies
CREATE INDEX idx_task_deps_task_id ON todos.task_dependencies(task_id);
CREATE INDEX idx_task_deps_depends_on_id ON todos.task_dependencies(depends_on_id);
CREATE INDEX idx_task_deps_type ON todos.task_dependencies(dependency_type);

-- Habits
CREATE INDEX idx_habits_area_id ON todos.habits(area_id);
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

CREATE TRIGGER areas_updated_at
    BEFORE UPDATE ON todos.areas
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER initiatives_updated_at
    BEFORE UPDATE ON todos.initiatives
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER key_results_updated_at
    BEFORE UPDATE ON todos.key_results
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER projects_updated_at
    BEFORE UPDATE ON todos.projects
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER tasks_updated_at
    BEFORE UPDATE ON todos.tasks
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();

CREATE TRIGGER habits_updated_at
    BEFORE UPDATE ON todos.habits
    FOR EACH ROW EXECUTE FUNCTION todos.update_updated_at();
