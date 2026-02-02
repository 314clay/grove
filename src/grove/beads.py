"""Beads integration for syncing with external issue trackers."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Bead:
    """A bead (issue) from an external beads repository."""
    id: str
    title: str
    description: Optional[str] = None
    status: str = "open"
    priority: int = 2
    issue_type: str = "task"
    assignee: Optional[str] = None
    owner: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None


def resolve_beads_path(beads_repo: str) -> Path:
    """Resolve a beads repo path to the actual .beads directory.

    Handles:
    - Absolute paths
    - Relative paths
    - Paths with redirect files
    """
    path = Path(beads_repo).expanduser()

    # If path ends with .beads, use it directly
    if path.name == ".beads":
        beads_dir = path
    else:
        # Otherwise, look for .beads subdirectory
        beads_dir = path / ".beads"

    # Check for redirect
    redirect_file = beads_dir / "redirect"
    if redirect_file.exists():
        redirect_target = redirect_file.read_text().strip()
        # Resolve redirect relative to the redirect file's directory
        beads_dir = (beads_dir / redirect_target).resolve()

    return beads_dir


def read_beads_jsonl(beads_dir: Path) -> list[Bead]:
    """Read beads from the issues.jsonl file in a beads directory.

    Args:
        beads_dir: Path to the .beads directory

    Returns:
        List of Bead objects

    Raises:
        FileNotFoundError: If issues.jsonl doesn't exist
    """
    jsonl_path = beads_dir / "issues.jsonl"
    if not jsonl_path.exists():
        raise FileNotFoundError(f"No issues.jsonl found at {jsonl_path}")

    beads = []
    with open(jsonl_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                bead = Bead(
                    id=data.get("id", ""),
                    title=data.get("title", ""),
                    description=data.get("description"),
                    status=data.get("status", "open"),
                    priority=data.get("priority", 2),
                    issue_type=data.get("issue_type", "task"),
                    assignee=data.get("assignee"),
                    owner=data.get("owner"),
                    created_at=data.get("created_at"),
                    updated_at=data.get("updated_at"),
                    created_by=data.get("created_by"),
                )
                beads.append(bead)
            except json.JSONDecodeError:
                continue  # Skip malformed lines

    return beads


def map_bead_status_to_task_status(bead_status: str) -> str:
    """Map a bead status to a task status.

    Bead statuses: open, in_progress, hooked, closed, etc.
    Task statuses: inbox, active, done, dropped
    """
    status_map = {
        "open": "inbox",
        "in_progress": "active",
        "hooked": "active",
        "closed": "done",
        "done": "done",
        "wont_fix": "dropped",
        "duplicate": "dropped",
    }
    return status_map.get(bead_status.lower(), "inbox")


def map_bead_priority_to_importance(priority: int) -> str:
    """Map bead priority (1-4) to task importance (high, medium, low).

    Priority 1 = urgent/high
    Priority 2 = high
    Priority 3 = medium
    Priority 4 = low
    """
    if priority <= 1:
        return "high"
    elif priority <= 2:
        return "high"
    elif priority <= 3:
        return "medium"
    else:
        return "low"


def map_task_status_to_bead_status(task_status: str) -> str:
    """Map a task status to a bead status.

    Task statuses: inbox, active, done, dropped
    Bead statuses: open, in_progress, closed, wont_fix
    """
    status_map = {
        "inbox": "open",
        "active": "in_progress",
        "done": "closed",
        "dropped": "wont_fix",
    }
    return status_map.get(task_status.lower(), "open")


def map_task_priority_to_bead_priority(priority: str) -> int:
    """Map task priority string to bead priority number.

    Task priorities: urgent, high, medium, low
    Bead priorities: 1, 2, 3, 4
    """
    priority_map = {
        "urgent": 1,
        "high": 2,
        "medium": 3,
        "low": 4,
    }
    return priority_map.get(priority.lower(), 3)


def get_bead_by_id(beads_dir: Path, bead_id: str) -> Optional[Bead]:
    """Get a specific bead by ID from the issues.jsonl file.

    Args:
        beads_dir: Path to the .beads directory
        bead_id: The bead ID to find

    Returns:
        Bead object if found, None otherwise
    """
    beads = read_beads_jsonl(beads_dir)
    for bead in beads:
        if bead.id == bead_id:
            return bead
    return None


def filter_open_beads(beads: list[Bead]) -> list[Bead]:
    """Filter to only open/active beads (not closed, done, etc.)."""
    open_statuses = {"open", "in_progress", "hooked"}
    return [b for b in beads if b.status.lower() in open_statuses]
