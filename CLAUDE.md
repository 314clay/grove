# Grove

Hierarchical task management CLI.

## Setup

```bash
export TODO_DATABASE_URL="postgresql://localhost/yourdb"
psql -d yourdb -f sql/schema.sql
```

## Commands

- `gv add "task"` - Add to inbox
- `gv inbox` - View inbox
- `gv now` - Actionable tasks
- `gv done <id>` - Complete task
- `gv overview` - Full hierarchy
