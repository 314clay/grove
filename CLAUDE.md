# Grove

Botanical task management CLI.

## Setup

```bash
export TODO_DATABASE_URL="postgresql://localhost/yourdb"
psql -d yourdb -f sql/schema.sql
```

## Naming Scheme

| Old | New | Description |
|-----|-----|-------------|
| Areas | **Groves** | Life domains |
| Initiatives | **Trunks** | Strategic goals |
| Projects | **Branches** | Finite deliverables |
| Tasks | **Buds** | Work items |
| Key Results | **Fruits** | Measurable outcomes |
| Inbox | **Seeds** | Unprocessed captures |
| Done | **Bloomed** | Completed |
| Dropped | **Mulch** | Abandoned |

## Bud Status Lifecycle

```
seed → dormant → budding → bloomed/mulch
```

## Commands

- `gv add "task"` - Plant a seed
- `gv seeds` - View inbox (alias: `gv inbox`)
- `gv pulse` - Actionable buds (alias: `gv now`)
- `gv bloom <id>` - Complete (alias: `gv done`)
- `gv mulch <id>` - Abandon
- `gv plant <id>` - Move seed to dormant
- `gv start <id>` - Move to budding
- `gv overview` - Full hierarchy
- `gv why <id>` - Trace hierarchy
- `gv review` - Weekly review flow
