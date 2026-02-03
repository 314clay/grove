# Grove

Botanical task management with hierarchical alignment and dependency tracking.

Grove combines GTD-style zero-friction capture with strategic goal alignment. Every task (bud) can trace its "why" up through branches, trunks, and groves.

## Philosophy

```
┌─────────────────────────────────────────────┐
│  GROVES (Life domains)                      │
│  Career, Health, Relationships, etc.        │
├─────────────────────────────────────────────┤
│  TRUNKS (Strategic initiatives)             │
│  "Get promoted", "Run a marathon"           │
├─────────────────────────────────────────────┤
│  FRUITS (Measurable outcomes)               │
│  "Ship 3 features", "Run 5K in 25 min"      │
├─────────────────────────────────────────────┤
│  BRANCHES (Projects)                        │
│  "Implement auth system", "Training plan"   │
├─────────────────────────────────────────────┤
│  BUDS (Tasks)                               │
│  "Review PR", "Morning run"                 │
│  Status: seed → dormant → budding → bloomed │
└─────────────────────────────────────────────┘
```

## Naming Scheme

| Concept | Name | Description |
|---------|------|-------------|
| Life domains | **Groves** | Forests where your work grows |
| Strategic goals | **Trunks** | Main stems supporting branches |
| Projects | **Branches** | Hold your buds |
| Tasks | **Buds** | Work items that bloom |
| Key Results | **Fruits** | Measurable outcomes that ripen |
| Inbox items | **Seeds** | Raw captures waiting to be planted |
| Completed | **Bloomed** | Work that has flowered |
| Abandoned | **Mulch** | Feeds future growth |

### Bud Lifecycle

```
seed → dormant → budding → bloomed
  │                          │
  └──────────────────────────┼──→ mulch (abandoned)
```

- **Seed**: Raw capture, unprocessed (inbox)
- **Dormant**: Clarified, ready to grow
- **Budding**: Actively being worked on
- **Bloomed**: Completed
- **Mulch**: Dropped/abandoned (nothing is wasted)

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
# Plant seeds (capture to inbox)
gv add "Review quarterly goals"
gv add "Fix login bug" --priority=high

# View seeds (inbox)
gv seeds

# Check the pulse (actionable, unblocked buds)
gv pulse

# Mark a bud as bloomed (complete)
gv bloom 1

# See the big picture
gv overview
```

## Commands

### Bud Management

| Command | Description |
|---------|-------------|
| `gv add "title"` | Plant a new seed (add to inbox) |
| `gv seeds` | Show unprocessed seeds |
| `gv list` | Show all budding (active) buds |
| `gv pulse` | Show actionable, unblocked buds |
| `gv bloom <id>` | Mark bud as bloomed (complete) |
| `gv mulch <id>` | Drop bud to mulch (abandon) |
| `gv start <id>` | Start budding (move to active) |
| `gv plant <id>` | Plant a seed (move to dormant) |

### Dependencies

| Command | Description |
|---------|-------------|
| `gv blocks <a> <b>` | Bud A blocks bud B |
| `gv chain <a> <b> <c>` | A → B → C (sequential) |
| `gv unblock <a> <b>` | Remove dependency |
| `gv blocked` | Show blocked buds |

### Hierarchy

| Command | Description |
|---------|-------------|
| `gv why <id>` | Trace bud → branch → trunk → grove |
| `gv overview` | Full hierarchy tree with progress |
| `gv branch new "name"` | Create branch (project) |
| `gv branch list` | List all branches |
| `gv trunk new "name"` | Create trunk (initiative) |
| `gv trunk list` | List all trunks |
| `gv grove new "name"` | Create grove (life area) |
| `gv grove list` | List all groves |

### Beads Integration

Grove integrates with [Beads](https://github.com/steveyegge/beads) for AI-native issue tracking in code projects.

```bash
# Link branch to beads repo
gv branch link <branch-id> ~/code/myproject

# Sync buds with beads
gv beads pull <branch-id>
gv beads push <branch-id>
gv beads sync <branch-id>
```

## Data Model

### Groves
Life domains that persist indefinitely: Career, Health, Relationships, Finance, etc.

### Trunks
Strategic initiatives within a grove. Time-bounded, outcome-focused.

### Fruits
Measurable outcomes (OKRs) that indicate trunk progress.

### Branches
Projects with clear completion criteria. Can link to beads repos.

### Buds
Individual work items. Can belong to branches, link directly to trunks/groves, or float freely as seeds.

### Dependencies
Buds can block other buds, forming a dependency graph. `gv pulse` shows only unblocked work.

## Database

Grove uses PostgreSQL with a `todos` schema:

```sql
-- Tables
todos.groves
todos.trunks
todos.fruits
todos.branches
todos.buds
todos.bud_dependencies
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

# Check seeds (inbox)
gv seeds

# Review blocked work
gv blocked

# Verify bud alignment
gv why <id>

# Run guided review
gv review
```

### Daily Workflow

```bash
# What can I do right now?
gv pulse

# Pick high-impact work
gv list --priority=high

# Mark progress
gv bloom <id>
```

## Backward Compatibility

For muscle memory, these aliases work:
- `gv inbox` → `gv seeds`
- `gv now` → `gv pulse`
- `gv done <id>` → `gv bloom <id>`

## License

MIT
