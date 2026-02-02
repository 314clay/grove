# Grove

Hierarchical task management with OKR alignment and dependency tracking.

Grove combines GTD-style zero-friction capture with strategic goal alignment. Every task can trace its "why" up through projects, initiatives, and life areas.

## Philosophy

```
┌─────────────────────────────────────────────┐
│  AREAS (Life domains)                       │
│  Career, Health, Relationships, etc.        │
├─────────────────────────────────────────────┤
│  INITIATIVES (Strategic goals)              │
│  "Get promoted", "Run a marathon"           │
├─────────────────────────────────────────────┤
│  KEY RESULTS (Measurable outcomes)          │
│  "Ship 3 features", "Run 5K in 25 min"      │
├─────────────────────────────────────────────┤
│  PROJECTS (Finite deliverables)             │
│  "Implement auth system", "Training plan"   │
├─────────────────────────────────────────────┤
│  TASKS (Actions)                            │
│  "Review PR", "Morning run"                 │
└─────────────────────────────────────────────┘
```

## Installation

```bash
# Clone and install
git clone https://github.com/yourusername/grove.git
cd grove
uv venv && source .venv/bin/activate
uv pip install -e .

# Set up database (PostgreSQL)
psql -d yourdb -f sql/schema.sql
export TODO_DATABASE_URL="postgresql://localhost/yourdb"
```

## Quick Start

```bash
# Capture tasks instantly (GTD inbox)
gv add "Review quarterly goals"
gv add "Fix login bug" --priority=high

# View inbox
gv inbox

# View actionable tasks (not blocked)
gv now

# Complete a task
gv done 1

# See the big picture
gv overview
```

## Commands

### Task Management

| Command | Description |
|---------|-------------|
| `gv add "title"` | Add task to inbox |
| `gv inbox` | Show unclarified inbox items |
| `gv list` | Show all active tasks |
| `gv now` | Show actionable, unblocked tasks |
| `gv done <id>` | Mark task complete |

### Dependencies

| Command | Description |
|---------|-------------|
| `gv blocks <a> <b>` | Task A blocks task B |
| `gv chain <a> <b> <c>` | A → B → C (sequential) |
| `gv unblock <a> <b>` | Remove dependency |
| `gv blocked` | Show blocked tasks |

### Hierarchy

| Command | Description |
|---------|-------------|
| `gv why <id>` | Trace task → project → initiative → area |
| `gv overview` | Full hierarchy tree with progress |
| `gv project new "name"` | Create project |
| `gv project list` | List all projects |

### Beads Integration

Grove integrates with [Beads](https://github.com/steveyegge/beads) for AI-native issue tracking in code projects.

```bash
# Link project to beads repo
gv beads link <project-id> ~/code/myproject

# Sync tasks with beads
gv beads pull <project-id>
gv beads push <task-id>
gv beads sync <project-id>
```

## Data Model

### Areas
Life domains that persist indefinitely: Career, Health, Relationships, Finance, etc.

### Initiatives
Strategic goals within an area. Time-bounded, outcome-focused.

### Key Results
Measurable outcomes that indicate initiative progress. OKR-style metrics.

### Projects
Finite deliverables with clear "done when" criteria. Can link to beads repos.

### Tasks
Individual actions. Can belong to projects, link directly to initiatives/areas, or float freely in inbox.

### Dependencies
Tasks can block other tasks, forming a dependency graph. `gv now` shows only unblocked work.

## Database

Grove uses PostgreSQL with a `todos` schema:

```sql
-- Tables
todos.areas
todos.initiatives
todos.key_results
todos.projects
todos.tasks
todos.task_dependencies
todos.habits
todos.habit_log
```

## Configuration

Set the database URL:

```bash
export TODO_DATABASE_URL="postgresql://localhost/yourdb"
```

## Workflows

### Weekly Review

```bash
# See everything
gv overview

# Check stale inbox items
gv inbox

# Review blocked work
gv blocked

# Verify task alignment
gv why <id>
```

### Daily Workflow

```bash
# What can I do right now?
gv now

# Pick high-impact work
gv list --priority=high

# Mark progress
gv done <id>
```

## License

MIT
