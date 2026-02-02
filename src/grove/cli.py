"""CLI entrypoint for the todo system."""

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option()
def main():
    """Grove - Personal todo system with hierarchical task management.
    
    Commands for managing tasks, projects, areas, and initiatives.
    """
    pass


@main.command()
@click.argument("title")
@click.option("--project", "-p", type=int, help="Assign to project ID")
@click.option("--priority", type=click.Choice(["urgent", "high", "medium", "low"]), default="medium", help="Task priority")
@click.option("--context", "-c", help="Context tag")
def add(title: str, project: int | None, priority: str, context: str | None):
    """Add a task to the inbox.

    Example: gv add "Review PR" --project=1 --priority=high
    """
    from grove.db import get_session
    from grove.models import Task

    with get_session() as session:
        task = Task(
            title=title,
            project_id=project,
            priority=priority,
            context=context,
            status="inbox",
        )
        session.add(task)
        session.commit()
        console.print(f"[green]Added:[/green] {task.title} (id: {task.id})")


@main.command()
def inbox():
    """Show unclarified inbox items."""
    from grove.db import get_session
    from grove.models import Task
    
    with get_session() as session:
        tasks = session.query(Task).filter(Task.status == "inbox").all()
        if not tasks:
            console.print("[dim]Inbox empty[/dim]")
            return
        for task in tasks:
            console.print(f"  {task.id}: {task.title}")


@main.command(name="list")
def list_tasks():
    """Show all actionable tasks."""
    from grove.db import get_session
    from grove.models import Task
    
    with get_session() as session:
        tasks = session.query(Task).filter(Task.status == "active").all()
        if not tasks:
            console.print("[dim]No active tasks[/dim]")
            return
        for task in tasks:
            console.print(f"  {task.id}: {task.title}")


@main.command()
def now():
    """Show actionable and unblocked tasks."""
    from sqlalchemy import and_, exists, select
    from grove.db import get_session
    from grove.models import Task, TaskDependency

    with get_session() as session:
        # Subquery: tasks that have incomplete blocking dependencies
        blocked_subq = select(TaskDependency.task_id).join(
            Task, TaskDependency.depends_on_id == Task.id
        ).where(
            and_(
                TaskDependency.dependency_type == "blocks",
                Task.status != "done"
            )
        ).scalar_subquery()

        # Get active tasks that are NOT blocked
        tasks = session.query(Task).filter(
            Task.status == "active",
            ~Task.id.in_(blocked_subq)
        ).all()

        if not tasks:
            console.print("[dim]Nothing to do right now[/dim]")
            return
        for task in tasks:
            console.print(f"  {task.id}: {task.title}")


@main.command()
@click.argument("task_id", type=int)
def done(task_id: int):
    """Mark a task as complete."""
    from grove.db import get_session
    from grove.models import Task

    with get_session() as session:
        task = session.query(Task).filter(Task.id == task_id).first()
        if not task:
            console.print(f"[red]Task not found:[/red] {task_id}")
            return
        task.status = "done"
        session.commit()
        console.print(f"[green]Completed:[/green] {task.title}")


@main.command()
@click.argument("blocker_id", type=int)
@click.argument("blocked_id", type=int)
def blocks(blocker_id: int, blocked_id: int):
    """Make one task block another.

    Example: gv blocks 1 2
    (task 1 must be completed before task 2 can start)
    """
    from grove.db import get_session
    from grove.models import Task, TaskDependency

    with get_session() as session:
        blocker = session.query(Task).filter(Task.id == blocker_id).first()
        blocked = session.query(Task).filter(Task.id == blocked_id).first()

        if not blocker:
            console.print(f"[red]Blocker task not found:[/red] {blocker_id}")
            return
        if not blocked:
            console.print(f"[red]Blocked task not found:[/red] {blocked_id}")
            return
        if blocker_id == blocked_id:
            console.print("[red]A task cannot block itself[/red]")
            return

        # Check if dependency already exists
        existing = session.query(TaskDependency).filter(
            TaskDependency.task_id == blocked_id,
            TaskDependency.depends_on_id == blocker_id
        ).first()

        if existing:
            console.print(f"[yellow]Dependency already exists[/yellow]")
            return

        dep = TaskDependency(
            task_id=blocked_id,
            depends_on_id=blocker_id,
            dependency_type="blocks"
        )
        session.add(dep)
        session.commit()
        console.print(f"[green]Created:[/green] {blocker.title} → blocks → {blocked.title}")


@main.command()
@click.argument("blocker_id", type=int)
@click.argument("blocked_id", type=int)
def unblock(blocker_id: int, blocked_id: int):
    """Remove a blocking relationship between tasks.

    Example: gv unblock 1 2
    """
    from grove.db import get_session
    from grove.models import TaskDependency

    with get_session() as session:
        dep = session.query(TaskDependency).filter(
            TaskDependency.task_id == blocked_id,
            TaskDependency.depends_on_id == blocker_id
        ).first()

        if not dep:
            console.print(f"[yellow]No blocking relationship found[/yellow]")
            return

        session.delete(dep)
        session.commit()
        console.print(f"[green]Removed:[/green] {blocker_id} no longer blocks {blocked_id}")


@main.command()
@click.argument("task_ids", nargs=-1, required=True, type=int)
def chain(task_ids: tuple):
    """Chain tasks in sequence (each blocks the next).

    Example: gv chain 1 2 3
    (1 → 2 → 3)
    """
    from grove.db import get_session
    from grove.models import Task, TaskDependency

    if len(task_ids) < 2:
        console.print("[red]Need at least 2 tasks to chain[/red]")
        return

    with get_session() as session:
        # Verify all tasks exist
        tasks = []
        for tid in task_ids:
            task = session.query(Task).filter(Task.id == tid).first()
            if not task:
                console.print(f"[red]Task not found:[/red] {tid}")
                return
            tasks.append(task)

        # Create chain of dependencies
        created = 0
        for i in range(len(tasks) - 1):
            blocker = tasks[i]
            blocked = tasks[i + 1]

            # Check if dependency already exists
            existing = session.query(TaskDependency).filter(
                TaskDependency.task_id == blocked.id,
                TaskDependency.depends_on_id == blocker.id
            ).first()

            if not existing:
                dep = TaskDependency(
                    task_id=blocked.id,
                    depends_on_id=blocker.id,
                    dependency_type="blocks"
                )
                session.add(dep)
                created += 1

        session.commit()

        chain_display = " → ".join(t.title for t in tasks)
        console.print(f"[green]Chained ({created} new):[/green] {chain_display}")


@main.command()
def blocked():
    """Show tasks that are blocked by incomplete tasks."""
    from grove.db import get_session
    from grove.models import Task, TaskDependency
    from sqlalchemy.orm import aliased

    with get_session() as session:
        # Find tasks that have incomplete blockers
        BlockingTask = aliased(Task)
        blocked_tasks = session.query(Task).join(
            TaskDependency, Task.id == TaskDependency.task_id
        ).join(
            BlockingTask, TaskDependency.depends_on_id == BlockingTask.id, isouter=True
        ).filter(
            TaskDependency.dependency_type == "blocks",
            BlockingTask.status != "done"
        ).distinct().all()

        if not blocked_tasks:
            console.print("[dim]No blocked tasks[/dim]")
            return

        for task in blocked_tasks:
            # Get what's blocking this task
            blockers = session.query(Task).join(
                TaskDependency, Task.id == TaskDependency.depends_on_id
            ).filter(
                TaskDependency.task_id == task.id,
                TaskDependency.dependency_type == "blocks",
                Task.status != "done"
            ).all()

            if blockers:
                blocker_titles = ", ".join(b.title for b in blockers)
                console.print(f"  {task.id}: {task.title}")
                console.print(f"    [dim]blocked by:[/dim] {blocker_titles}")


@main.command()
@click.argument("task_id", type=int)
def why(task_id: int):
    """Trace task up through project → initiative → area.

    Shows why a task exists by displaying its full hierarchy.
    Tasks can link directly to area/initiative or via project.

    Example: gv why 123
    """
    from grove.db import get_session
    from grove.models import Task, Project, Initiative, Area

    with get_session() as session:
        task = session.query(Task).filter(Task.id == task_id).first()
        if not task:
            console.print(f"[red]Task not found:[/red] {task_id}")
            return

        console.print()
        console.print(f"[bold cyan]Task:[/bold cyan] {task.title}")
        console.print(f"  [dim]id: {task.id} | status: {task.status} | priority: {task.priority}[/dim]")

        # Track what we've shown to avoid duplicates
        shown_project = False
        shown_initiative = False
        shown_area = False

        # Show project if linked
        if task.project_id:
            project = session.query(Project).filter(Project.id == task.project_id).first()
            if project:
                shown_project = True
                console.print()
                console.print(f"  [bold yellow]↑ Project:[/bold yellow] {project.title}")
                console.print(f"    [dim]id: {project.id} | status: {project.status}[/dim]")
                if project.done_when:
                    console.print(f"    [dim]done when: {project.done_when}[/dim]")

                # Show initiative via project
                if project.initiative_id:
                    initiative = session.query(Initiative).filter(Initiative.id == project.initiative_id).first()
                    if initiative:
                        shown_initiative = True
                        console.print()
                        console.print(f"    [bold magenta]↑ Initiative:[/bold magenta] {initiative.title}")
                        console.print(f"      [dim]id: {initiative.id} | status: {initiative.status}[/dim]")
                        if initiative.target_date:
                            console.print(f"      [dim]target: {initiative.target_date.strftime('%Y-%m-%d')}[/dim]")

                        # Show area via initiative
                        if initiative.area_id:
                            area = session.query(Area).filter(Area.id == initiative.area_id).first()
                            if area:
                                shown_area = True
                                icon = area.icon or "📁"
                                console.print()
                                console.print(f"      [bold green]↑ Area:[/bold green] {icon} {area.name}")
                                console.print(f"        [dim]id: {area.id}[/dim]")
                                if area.description:
                                    console.print(f"        [dim]{area.description}[/dim]")

        # Show direct initiative link if not shown via project
        if task.initiative_id and not shown_initiative:
            initiative = session.query(Initiative).filter(Initiative.id == task.initiative_id).first()
            if initiative:
                shown_initiative = True
                console.print()
                console.print(f"  [bold magenta]↑ Initiative (direct):[/bold magenta] {initiative.title}")
                console.print(f"    [dim]id: {initiative.id} | status: {initiative.status}[/dim]")
                if initiative.target_date:
                    console.print(f"    [dim]target: {initiative.target_date.strftime('%Y-%m-%d')}[/dim]")

                # Show area via direct initiative
                if initiative.area_id and not shown_area:
                    area = session.query(Area).filter(Area.id == initiative.area_id).first()
                    if area:
                        shown_area = True
                        icon = area.icon or "📁"
                        console.print()
                        console.print(f"    [bold green]↑ Area:[/bold green] {icon} {area.name}")
                        console.print(f"      [dim]id: {area.id}[/dim]")
                        if area.description:
                            console.print(f"      [dim]{area.description}[/dim]")

        # Show direct area link if not shown via initiative
        if task.area_id and not shown_area:
            area = session.query(Area).filter(Area.id == task.area_id).first()
            if area:
                icon = area.icon or "📁"
                console.print()
                console.print(f"  [bold green]↑ Area (direct):[/bold green] {icon} {area.name}")
                console.print(f"    [dim]id: {area.id}[/dim]")
                if area.description:
                    console.print(f"    [dim]{area.description}[/dim]")

        # If no links at all
        if not task.project_id and not task.initiative_id and not task.area_id:
            console.print()
            console.print("[dim]This task is not linked to any project, initiative, or area.[/dim]")

        console.print()


@main.group()
def project():
    """Manage projects."""
    pass


@project.command()
@click.argument("project_id", type=int)
@click.argument("beads_path")
def link(project_id: int, beads_path: str):
    """Link a project to a beads repository path.

    Sets the beads_repo field on a project, enabling beads integration
    for tracking AI-native issues associated with this project.

    Example: gv project link 1 /path/to/.beads
    Example: gv project link 1 ../shared/.beads
    """
    import os
    from grove.db import get_session
    from grove.models import Project

    with get_session() as session:
        proj = session.query(Project).filter(Project.id == project_id).first()
        if not proj:
            console.print(f"[red]Project not found:[/red] {project_id}")
            return

        # Resolve relative paths to absolute
        if not os.path.isabs(beads_path):
            beads_path = os.path.abspath(beads_path)

        proj.beads_repo = beads_path
        session.commit()
        console.print(f"[green]Linked:[/green] {proj.title} → {beads_path}")


@project.command(name="list")
def list_projects():
    """List all projects with their beads links."""
    from grove.db import get_session
    from grove.models import Project

    with get_session() as session:
        projects = session.query(Project).order_by(Project.title).all()
        if not projects:
            console.print("[dim]No projects[/dim]")
            return

        for proj in projects:
            status_icon = "●" if proj.status == "done" else "○"
            beads_info = f" → {proj.beads_repo}" if proj.beads_repo else ""
            console.print(f"  {proj.id}: {status_icon} {proj.title}[dim]{beads_info}[/dim]")


@project.command()
@click.argument("project_id", type=int)
def show(project_id: int):
    """Show project details including beads link."""
    from grove.db import get_session
    from grove.models import Project, Task

    with get_session() as session:
        proj = session.query(Project).filter(Project.id == project_id).first()
        if not proj:
            console.print(f"[red]Project not found:[/red] {project_id}")
            return

        console.print()
        console.print(f"[bold yellow]Project:[/bold yellow] {proj.title}")
        console.print(f"  [dim]id: {proj.id} | status: {proj.status} | priority: {proj.priority}[/dim]")
        if proj.description:
            console.print(f"  [dim]{proj.description}[/dim]")
        if proj.done_when:
            console.print(f"  [dim]done when: {proj.done_when}[/dim]")
        if proj.target_date:
            console.print(f"  [dim]target: {proj.target_date.strftime('%Y-%m-%d')}[/dim]")
        if proj.beads_repo:
            console.print(f"  [cyan]beads:[/cyan] {proj.beads_repo}")
        else:
            console.print(f"  [dim]beads: not linked[/dim]")

        # Show task count
        task_count = session.query(Task).filter(Task.project_id == proj.id).count()
        done_count = session.query(Task).filter(Task.project_id == proj.id, Task.status == "done").count()
        console.print(f"  [dim]tasks: {done_count}/{task_count}[/dim]")
        console.print()


@project.command()
@click.argument("project_id", type=int)
def unlink(project_id: int):
    """Remove beads link from a project."""
    from grove.db import get_session
    from grove.models import Project

    with get_session() as session:
        proj = session.query(Project).filter(Project.id == project_id).first()
        if not proj:
            console.print(f"[red]Project not found:[/red] {project_id}")
            return

        if not proj.beads_repo:
            console.print(f"[yellow]Project not linked to beads[/yellow]")
            return

        old_path = proj.beads_repo
        proj.beads_repo = None
        session.commit()
        console.print(f"[green]Unlinked:[/green] {proj.title} (was: {old_path})")


@main.group()
def beads():
    """Beads integration commands for syncing with AI-native issue tracking."""
    pass


@beads.command()
@click.argument("project_id", type=int)
@click.argument("task_ids", nargs=-1, type=int)
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without creating issues")
def push(project_id: int, task_ids: tuple, dry_run: bool):
    """Push tasks to beads in the linked repository.

    Exports tasks from a project as beads issues. If task_ids are provided,
    only those tasks are pushed. Otherwise, all active tasks in the project
    are pushed.

    Example: gv beads push 1
    Example: gv beads push 1 10 11 12
    """
    import os
    import subprocess
    from grove.db import get_session
    from grove.models import Project, Task

    with get_session() as session:
        proj = session.query(Project).filter(Project.id == project_id).first()
        if not proj:
            console.print(f"[red]Project not found:[/red] {project_id}")
            return

        if not proj.beads_repo:
            console.print(f"[red]Project not linked to beads.[/red] Use 't project link' first.")
            return

        # Verify beads path exists
        beads_path = proj.beads_repo
        if not os.path.isdir(beads_path):
            console.print(f"[red]Beads directory not found:[/red] {beads_path}")
            return

        # Get tasks to push
        if task_ids:
            tasks = session.query(Task).filter(
                Task.id.in_(task_ids),
                Task.project_id == project_id
            ).all()
            if len(tasks) != len(task_ids):
                found_ids = {t.id for t in tasks}
                missing = [tid for tid in task_ids if tid not in found_ids]
                console.print(f"[yellow]Warning: Tasks not found in project: {missing}[/yellow]")
        else:
            # Get all active tasks in the project
            tasks = session.query(Task).filter(
                Task.project_id == project_id,
                Task.status.in_(["inbox", "active"])
            ).all()

        if not tasks:
            console.print("[dim]No tasks to push[/dim]")
            return

        console.print(f"[cyan]Pushing {len(tasks)} task(s) to:[/cyan] {beads_path}")
        console.print()

        # Map priority strings to beads priority numbers
        priority_map = {
            "urgent": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
        }

        pushed = 0
        for task in tasks:
            # Build bd create command
            cmd = [
                "bd", "create",
                "--db", os.path.join(beads_path, "beads.db"),
                "--title", task.title,
                "--priority", str(priority_map.get(task.priority, 3)),
                "--type", "task",
            ]

            # Add description if present
            if task.description:
                cmd.extend(["--description", task.description])

            # Add notes about source
            source_note = f"Imported from t task #{task.id}"
            if task.context:
                source_note += f" (context: {task.context})"
            cmd.extend(["--notes", source_note])

            if dry_run:
                console.print(f"  [dim]Would create:[/dim] {task.title}")
                console.print(f"    [dim]cmd: {' '.join(cmd)}[/dim]")
            else:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        cwd=os.path.dirname(beads_path)  # Run from parent of .beads
                    )
                    if result.returncode == 0:
                        # Extract the created issue ID from output
                        output = result.stdout.strip()
                        console.print(f"  [green]Created:[/green] {task.title}")
                        if output:
                            console.print(f"    [dim]{output}[/dim]")
                        pushed += 1
                    else:
                        console.print(f"  [red]Failed:[/red] {task.title}")
                        if result.stderr:
                            console.print(f"    [dim]{result.stderr}[/dim]")
                except Exception as e:
                    console.print(f"  [red]Error:[/red] {task.title} - {e}")

        console.print()
        if dry_run:
            console.print(f"[dim]Dry run complete. Would push {len(tasks)} task(s).[/dim]")
        else:
            console.print(f"[green]Pushed {pushed}/{len(tasks)} task(s)[/green]")


@main.command()
def overview():
    """Show full hierarchy tree with counts and progress.

    Displays all areas, initiatives, projects, and task counts.

    Example: gv overview
    """
    from sqlalchemy import func
    from grove.db import get_session
    from grove.models import Area, Initiative, Project, Task

    with get_session() as session:
        # Get all areas
        areas = session.query(Area).order_by(Area.name).all()

        # Get orphan initiatives (no area)
        orphan_initiatives = session.query(Initiative).filter(
            Initiative.area_id.is_(None)
        ).order_by(Initiative.title).all()

        # Get orphan projects (no initiative)
        orphan_projects = session.query(Project).filter(
            Project.initiative_id.is_(None)
        ).order_by(Project.title).all()

        # Get orphan tasks (no project)
        orphan_tasks = session.query(Task).filter(
            Task.project_id.is_(None),
            Task.status != "done"
        ).all()

        console.print()
        console.print("[bold]Todo System Overview[/bold]")
        console.print("=" * 40)

        for area in areas:
            icon = area.icon or "📁"
            initiatives = session.query(Initiative).filter(Initiative.area_id == area.id).all()

            # Count all tasks under this area
            area_task_count = 0
            area_done_count = 0

            for init in initiatives:
                projects = session.query(Project).filter(Project.initiative_id == init.id).all()
                for proj in projects:
                    tasks = session.query(Task).filter(Task.project_id == proj.id).all()
                    area_task_count += len(tasks)
                    area_done_count += len([t for t in tasks if t.status == "done"])

            progress = f"{area_done_count}/{area_task_count}" if area_task_count > 0 else "0/0"
            console.print()
            console.print(f"[bold green]{icon} {area.name}[/bold green] [{progress}]")

            for init in initiatives:
                projects = session.query(Project).filter(Project.initiative_id == init.id).all()

                # Count tasks for this initiative
                init_task_count = 0
                init_done_count = 0
                for proj in projects:
                    tasks = session.query(Task).filter(Task.project_id == proj.id).all()
                    init_task_count += len(tasks)
                    init_done_count += len([t for t in tasks if t.status == "done"])

                progress = f"{init_done_count}/{init_task_count}" if init_task_count > 0 else "0/0"
                status_icon = "○" if init.status == "active" else "●"
                console.print(f"  {status_icon} [magenta]{init.title}[/magenta] [{progress}]")

                for proj in projects:
                    tasks = session.query(Task).filter(Task.project_id == proj.id).all()
                    done_count = len([t for t in tasks if t.status == "done"])
                    total_count = len(tasks)
                    progress = f"{done_count}/{total_count}" if total_count > 0 else "0/0"
                    status_icon = "○" if proj.status == "active" else "●"
                    console.print(f"    {status_icon} [yellow]{proj.title}[/yellow] [{progress}]")

        # Show orphans
        if orphan_initiatives:
            console.print()
            console.print("[bold dim]Unassigned Initiatives[/bold dim]")
            for init in orphan_initiatives:
                projects = session.query(Project).filter(Project.initiative_id == init.id).all()
                init_task_count = 0
                init_done_count = 0
                for proj in projects:
                    tasks = session.query(Task).filter(Task.project_id == proj.id).all()
                    init_task_count += len(tasks)
                    init_done_count += len([t for t in tasks if t.status == "done"])
                progress = f"{init_done_count}/{init_task_count}" if init_task_count > 0 else "0/0"
                console.print(f"  ○ [magenta]{init.title}[/magenta] [{progress}]")

        if orphan_projects:
            console.print()
            console.print("[bold dim]Unassigned Projects[/bold dim]")
            for proj in orphan_projects:
                tasks = session.query(Task).filter(Task.project_id == proj.id).all()
                done_count = len([t for t in tasks if t.status == "done"])
                total_count = len(tasks)
                progress = f"{done_count}/{total_count}" if total_count > 0 else "0/0"
                console.print(f"  ○ [yellow]{proj.title}[/yellow] [{progress}]")

        if orphan_tasks:
            console.print()
            console.print(f"[bold dim]Unassigned Tasks[/bold dim] [{len(orphan_tasks)} items]")
            for task in orphan_tasks[:5]:  # Show first 5
                console.print(f"  • [dim]{task.title}[/dim]")
            if len(orphan_tasks) > 5:
                console.print(f"  [dim]... and {len(orphan_tasks) - 5} more[/dim]")

        # Summary stats
        total_tasks = session.query(Task).count()
        done_tasks = session.query(Task).filter(Task.status == "done").count()
        active_tasks = session.query(Task).filter(Task.status == "active").count()
        inbox_tasks = session.query(Task).filter(Task.status == "inbox").count()

        console.print()
        console.print("=" * 40)
        console.print(f"[bold]Total:[/bold] {total_tasks} tasks | "
                      f"[green]{done_tasks} done[/green] | "
                      f"[cyan]{active_tasks} active[/cyan] | "
                      f"[yellow]{inbox_tasks} inbox[/yellow]")
        console.print()


if __name__ == "__main__":
    main()
