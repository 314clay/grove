"""CLI entrypoint for Grove - botanical task management.

Naming scheme:
- Groves: Life domains
- Trunks: Strategic initiatives
- Branches: Projects
- Buds: Tasks (status: seed → dormant → budding → bloomed/mulch)
- Fruits: Key results (OKRs)
- Seeds: Unprocessed buds (gv seeds command)
- Pulse: Check what's actionable (gv pulse command)
"""

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option()
def main():
    """Grove - Botanical task management with hierarchical alignment.

    Your work grows from seeds to blooming buds on branches,
    supported by trunks, all within your groves.

    Commands for managing buds, branches, trunks, and groves.
    """
    pass


# =============================================================================
# BUD MANAGEMENT (Tasks)
# =============================================================================


@main.command()
@click.argument("title")
@click.option("--branch", "-b", type=int, help="Plant on branch (project) ID")
@click.option("--priority", type=click.Choice(["urgent", "high", "medium", "low"]), default="medium", help="Bud priority")
@click.option("--context", "-c", help="Context tag")
def add(title: str, branch: int | None, priority: str, context: str | None):
    """Plant a new seed (add to inbox).

    Seeds are raw captures that haven't been clarified yet.
    Process them with 'gv seeds' to decide what they become.

    Example: gv add "Review PR" --branch=1 --priority=high
    """
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        bud = Bud(
            title=title,
            branch_id=branch,
            priority=priority,
            context=context,
            status="seed",
        )
        session.add(bud)
        session.commit()
        console.print(f"[green]Planted seed:[/green] {bud.title} (id: {bud.id})")


@main.command()
def seeds():
    """Show unprocessed seeds (inbox items).

    Seeds are raw captures waiting to be clarified.
    Decide: Is this a bud? A new branch? Or mulch?
    """
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        buds = session.query(Bud).filter(Bud.status == "seed").all()
        if not buds:
            console.print("[dim]No seeds to process[/dim]")
            return
        console.print("[bold]Seeds (unprocessed):[/bold]")
        for bud in buds:
            console.print(f"  {bud.id}: {bud.title}")


@main.command(name="list")
def list_buds():
    """Show all budding (active) work."""
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        buds = session.query(Bud).filter(Bud.status == "budding").all()
        if not buds:
            console.print("[dim]No buds currently growing[/dim]")
            return
        console.print("[bold]Budding (in progress):[/bold]")
        for bud in buds:
            console.print(f"  {bud.id}: {bud.title}")


@main.command()
def pulse():
    """Check the pulse - show actionable, unblocked buds.

    These are buds that are budding (active) and not blocked
    by other incomplete buds.
    """
    from sqlalchemy import and_, select
    from grove.db import get_session
    from grove.models import Bud, BudDependency

    with get_session() as session:
        # Subquery: buds that have incomplete blocking dependencies
        blocked_subq = select(BudDependency.bud_id).join(
            Bud, BudDependency.depends_on_id == Bud.id
        ).where(
            and_(
                BudDependency.dependency_type == "blocks",
                Bud.status != "bloomed"
            )
        ).scalar_subquery()

        # Get budding buds that are NOT blocked
        buds = session.query(Bud).filter(
            Bud.status == "budding",
            ~Bud.id.in_(blocked_subq)
        ).all()

        if not buds:
            console.print("[dim]Nothing ready to work on right now[/dim]")
            return
        console.print("[bold]Ready to bloom:[/bold]")
        for bud in buds:
            console.print(f"  {bud.id}: {bud.title}")


@main.command()
@click.argument("bud_id", type=int)
def bloom(bud_id: int):
    """Mark a bud as bloomed (complete).

    Example: gv bloom 1
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        bud = session.query(Bud).filter(Bud.id == bud_id).first()
        if not bud:
            console.print(f"[red]Bud not found:[/red] {bud_id}")
            return
        bud.status = "bloomed"
        bud.completed_at = datetime.utcnow()
        session.commit()
        console.print(f"[green]🌸 Bloomed:[/green] {bud.title}")


@main.command()
@click.argument("bud_id", type=int)
def mulch(bud_id: int):
    """Drop a bud to the mulch (abandon it).

    Mulched buds feed future growth - nothing is wasted.

    Example: gv mulch 1
    """
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        bud = session.query(Bud).filter(Bud.id == bud_id).first()
        if not bud:
            console.print(f"[red]Bud not found:[/red] {bud_id}")
            return
        bud.status = "mulch"
        session.commit()
        console.print(f"[yellow]Mulched:[/yellow] {bud.title}")


@main.command()
@click.argument("bud_id", type=int)
def start(bud_id: int):
    """Start working on a bud (move to budding status).

    Example: gv start 1
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        bud = session.query(Bud).filter(Bud.id == bud_id).first()
        if not bud:
            console.print(f"[red]Bud not found:[/red] {bud_id}")
            return
        if bud.status == "budding":
            console.print(f"[yellow]Already budding:[/yellow] {bud.title}")
            return
        bud.status = "budding"
        bud.started_at = datetime.utcnow()
        session.commit()
        console.print(f"[green]Started budding:[/green] {bud.title}")


@main.command()
@click.argument("bud_id", type=int)
def plant(bud_id: int):
    """Plant a seed (move from seed to dormant status).

    This clarifies a seed - it's now a proper bud, ready to grow.

    Example: gv plant 1
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        bud = session.query(Bud).filter(Bud.id == bud_id).first()
        if not bud:
            console.print(f"[red]Bud not found:[/red] {bud_id}")
            return
        if bud.status != "seed":
            console.print(f"[yellow]Not a seed:[/yellow] {bud.title} (status: {bud.status})")
            return
        bud.status = "dormant"
        bud.clarified_at = datetime.utcnow()
        session.commit()
        console.print(f"[green]Planted:[/green] {bud.title} (now dormant, ready to grow)")


# =============================================================================
# DEPENDENCIES
# =============================================================================


@main.command()
@click.argument("blocker_id", type=int)
@click.argument("blocked_id", type=int)
def blocks(blocker_id: int, blocked_id: int):
    """Make one bud block another.

    The first bud must bloom before the second can start.

    Example: gv blocks 1 2
    (bud 1 must bloom before bud 2 can start)
    """
    from grove.db import get_session
    from grove.models import Bud, BudDependency

    with get_session() as session:
        blocker = session.query(Bud).filter(Bud.id == blocker_id).first()
        blocked = session.query(Bud).filter(Bud.id == blocked_id).first()

        if not blocker:
            console.print(f"[red]Blocker bud not found:[/red] {blocker_id}")
            return
        if not blocked:
            console.print(f"[red]Blocked bud not found:[/red] {blocked_id}")
            return
        if blocker_id == blocked_id:
            console.print("[red]A bud cannot block itself[/red]")
            return

        # Check if dependency already exists
        existing = session.query(BudDependency).filter(
            BudDependency.bud_id == blocked_id,
            BudDependency.depends_on_id == blocker_id
        ).first()

        if existing:
            console.print("[yellow]Dependency already exists[/yellow]")
            return

        dep = BudDependency(
            bud_id=blocked_id,
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
    """Remove a blocking relationship between buds.

    Example: gv unblock 1 2
    """
    from grove.db import get_session
    from grove.models import BudDependency

    with get_session() as session:
        dep = session.query(BudDependency).filter(
            BudDependency.bud_id == blocked_id,
            BudDependency.depends_on_id == blocker_id
        ).first()

        if not dep:
            console.print("[yellow]No blocking relationship found[/yellow]")
            return

        session.delete(dep)
        session.commit()
        console.print(f"[green]Removed:[/green] {blocker_id} no longer blocks {blocked_id}")


@main.command()
@click.argument("bud_ids", nargs=-1, required=True, type=int)
def chain(bud_ids: tuple):
    """Chain buds in sequence (each blocks the next).

    Example: gv chain 1 2 3
    (1 must bloom before 2, 2 must bloom before 3)
    """
    from grove.db import get_session
    from grove.models import Bud, BudDependency

    if len(bud_ids) < 2:
        console.print("[red]Need at least 2 buds to chain[/red]")
        return

    with get_session() as session:
        # Verify all buds exist
        buds = []
        for bid in bud_ids:
            bud = session.query(Bud).filter(Bud.id == bid).first()
            if not bud:
                console.print(f"[red]Bud not found:[/red] {bid}")
                return
            buds.append(bud)

        # Create chain of dependencies
        created = 0
        for i in range(len(buds) - 1):
            blocker = buds[i]
            blocked = buds[i + 1]

            # Check if dependency already exists
            existing = session.query(BudDependency).filter(
                BudDependency.bud_id == blocked.id,
                BudDependency.depends_on_id == blocker.id
            ).first()

            if not existing:
                dep = BudDependency(
                    bud_id=blocked.id,
                    depends_on_id=blocker.id,
                    dependency_type="blocks"
                )
                session.add(dep)
                created += 1

        session.commit()

        chain_display = " → ".join(b.title for b in buds)
        console.print(f"[green]Chained ({created} new):[/green] {chain_display}")


@main.command()
def blocked():
    """Show buds that are blocked by incomplete buds."""
    from grove.db import get_session
    from grove.models import Bud, BudDependency
    from sqlalchemy.orm import aliased

    with get_session() as session:
        # Find buds that have incomplete blockers
        BlockingBud = aliased(Bud)
        blocked_buds = session.query(Bud).join(
            BudDependency, Bud.id == BudDependency.bud_id
        ).join(
            BlockingBud, BudDependency.depends_on_id == BlockingBud.id, isouter=True
        ).filter(
            BudDependency.dependency_type == "blocks",
            BlockingBud.status != "bloomed"
        ).distinct().all()

        if not blocked_buds:
            console.print("[dim]No blocked buds[/dim]")
            return

        console.print("[bold]Blocked buds:[/bold]")
        for bud in blocked_buds:
            # Get what's blocking this bud
            blockers = session.query(Bud).join(
                BudDependency, Bud.id == BudDependency.depends_on_id
            ).filter(
                BudDependency.bud_id == bud.id,
                BudDependency.dependency_type == "blocks",
                Bud.status != "bloomed"
            ).all()

            if blockers:
                blocker_titles = ", ".join(b.title for b in blockers)
                console.print(f"  {bud.id}: {bud.title}")
                console.print(f"    [dim]waiting for:[/dim] {blocker_titles}")


# =============================================================================
# WHY - Trace hierarchy
# =============================================================================


@main.command()
@click.argument("bud_id", type=int)
def why(bud_id: int):
    """Trace a bud up through branch → trunk → grove.

    Shows why a bud exists by displaying its full hierarchy.
    Buds can link directly to grove/trunk or via branch.

    Example: gv why 123
    """
    from grove.db import get_session
    from grove.models import Bud, Branch, Trunk, Grove

    with get_session() as session:
        bud = session.query(Bud).filter(Bud.id == bud_id).first()
        if not bud:
            console.print(f"[red]Bud not found:[/red] {bud_id}")
            return

        console.print()
        console.print(f"[bold cyan]Bud:[/bold cyan] {bud.title}")
        console.print(f"  [dim]id: {bud.id} | status: {bud.status} | priority: {bud.priority}[/dim]")

        # Track what we've shown to avoid duplicates
        shown_branch = False
        shown_trunk = False
        shown_grove = False

        # Show branch if linked
        if bud.branch_id:
            branch = session.query(Branch).filter(Branch.id == bud.branch_id).first()
            if branch:
                shown_branch = True
                console.print()
                console.print(f"  [bold yellow]↑ Branch:[/bold yellow] {branch.title}")
                console.print(f"    [dim]id: {branch.id} | status: {branch.status}[/dim]")
                if branch.done_when:
                    console.print(f"    [dim]blooms when: {branch.done_when}[/dim]")

                # Show trunk via branch
                if branch.trunk_id:
                    trunk = session.query(Trunk).filter(Trunk.id == branch.trunk_id).first()
                    if trunk:
                        shown_trunk = True
                        console.print()
                        console.print(f"    [bold magenta]↑ Trunk:[/bold magenta] {trunk.title}")
                        console.print(f"      [dim]id: {trunk.id} | status: {trunk.status}[/dim]")
                        if trunk.target_date:
                            console.print(f"      [dim]target: {trunk.target_date.strftime('%Y-%m-%d')}[/dim]")

                        # Show grove via trunk
                        if trunk.grove_id:
                            grove = session.query(Grove).filter(Grove.id == trunk.grove_id).first()
                            if grove:
                                shown_grove = True
                                icon = grove.icon or "🌳"
                                console.print()
                                console.print(f"      [bold green]↑ Grove:[/bold green] {icon} {grove.name}")
                                console.print(f"        [dim]id: {grove.id}[/dim]")
                                if grove.description:
                                    console.print(f"        [dim]{grove.description}[/dim]")

        # Show direct trunk link if not shown via branch
        if bud.trunk_id and not shown_trunk:
            trunk = session.query(Trunk).filter(Trunk.id == bud.trunk_id).first()
            if trunk:
                shown_trunk = True
                console.print()
                console.print(f"  [bold magenta]↑ Trunk (direct):[/bold magenta] {trunk.title}")
                console.print(f"    [dim]id: {trunk.id} | status: {trunk.status}[/dim]")
                if trunk.target_date:
                    console.print(f"    [dim]target: {trunk.target_date.strftime('%Y-%m-%d')}[/dim]")

                # Show grove via direct trunk
                if trunk.grove_id and not shown_grove:
                    grove = session.query(Grove).filter(Grove.id == trunk.grove_id).first()
                    if grove:
                        shown_grove = True
                        icon = grove.icon or "🌳"
                        console.print()
                        console.print(f"    [bold green]↑ Grove:[/bold green] {icon} {grove.name}")
                        console.print(f"      [dim]id: {grove.id}[/dim]")
                        if grove.description:
                            console.print(f"      [dim]{grove.description}[/dim]")

        # Show direct grove link if not shown via trunk
        if bud.grove_id and not shown_grove:
            grove = session.query(Grove).filter(Grove.id == bud.grove_id).first()
            if grove:
                icon = grove.icon or "🌳"
                console.print()
                console.print(f"  [bold green]↑ Grove (direct):[/bold green] {icon} {grove.name}")
                console.print(f"    [dim]id: {grove.id}[/dim]")
                if grove.description:
                    console.print(f"    [dim]{grove.description}[/dim]")

        # If no links at all
        if not bud.branch_id and not bud.trunk_id and not bud.grove_id:
            console.print()
            console.print("[dim]This bud is not planted on any branch, trunk, or grove.[/dim]")

        console.print()


# =============================================================================
# BRANCH (Project) MANAGEMENT
# =============================================================================


@main.group()
def branch():
    """Manage branches (projects)."""
    pass


@branch.command()
@click.argument("branch_id", type=int)
@click.argument("beads_path")
def link(branch_id: int, beads_path: str):
    """Link a branch to a beads repository path.

    Sets the beads_repo field on a branch, enabling beads integration
    for tracking AI-native issues associated with this branch.

    Example: gv branch link 1 /path/to/.beads
    Example: gv branch link 1 ../shared/.beads
    """
    import os
    from grove.db import get_session
    from grove.models import Branch

    with get_session() as session:
        br = session.query(Branch).filter(Branch.id == branch_id).first()
        if not br:
            console.print(f"[red]Branch not found:[/red] {branch_id}")
            return

        # Resolve relative paths to absolute
        if not os.path.isabs(beads_path):
            beads_path = os.path.abspath(beads_path)

        br.beads_repo = beads_path
        session.commit()
        console.print(f"[green]Linked:[/green] {br.title} → {beads_path}")


@branch.command(name="list")
def list_branches():
    """List all branches with their beads links."""
    from grove.db import get_session
    from grove.models import Branch

    with get_session() as session:
        branches = session.query(Branch).order_by(Branch.title).all()
        if not branches:
            console.print("[dim]No branches[/dim]")
            return

        console.print("[bold]Branches:[/bold]")
        for br in branches:
            status_icon = "●" if br.status == "completed" else "○"
            beads_info = f" → {br.beads_repo}" if br.beads_repo else ""
            console.print(f"  {br.id}: {status_icon} {br.title}[dim]{beads_info}[/dim]")


@branch.command()
@click.argument("branch_id", type=int)
def show(branch_id: int):
    """Show branch details including beads link."""
    from grove.db import get_session
    from grove.models import Branch, Bud

    with get_session() as session:
        br = session.query(Branch).filter(Branch.id == branch_id).first()
        if not br:
            console.print(f"[red]Branch not found:[/red] {branch_id}")
            return

        console.print()
        console.print(f"[bold yellow]Branch:[/bold yellow] {br.title}")
        console.print(f"  [dim]id: {br.id} | status: {br.status} | priority: {br.priority}[/dim]")
        if br.description:
            console.print(f"  [dim]{br.description}[/dim]")
        if br.done_when:
            console.print(f"  [dim]blooms when: {br.done_when}[/dim]")
        if br.target_date:
            console.print(f"  [dim]target: {br.target_date.strftime('%Y-%m-%d')}[/dim]")
        if br.beads_repo:
            console.print(f"  [cyan]beads:[/cyan] {br.beads_repo}")
        else:
            console.print("  [dim]beads: not linked[/dim]")

        # Show bud count
        bud_count = session.query(Bud).filter(Bud.branch_id == br.id).count()
        bloomed_count = session.query(Bud).filter(Bud.branch_id == br.id, Bud.status == "bloomed").count()
        console.print(f"  [dim]buds: {bloomed_count}/{bud_count} bloomed[/dim]")
        console.print()


@branch.command(name="new")
@click.argument("title")
@click.option("--trunk", "-t", "trunk_id", type=int, help="Link to trunk ID")
@click.option("--grove", "-g", "grove_id", type=int, help="Link to grove ID")
@click.option("--description", "-d", help="Branch description")
@click.option("--done-when", help="Completion criteria")
def branch_new(title: str, trunk_id: int | None, grove_id: int | None, description: str | None, done_when: str | None):
    """Create a new branch (project).

    Example: gv branch new "Auth System" --trunk=1
    Example: gv branch new "Side Project" --grove=2
    """
    from grove.db import get_session
    from grove.models import Branch, Trunk, Grove

    with get_session() as session:
        if trunk_id:
            trunk = session.query(Trunk).filter(Trunk.id == trunk_id).first()
            if not trunk:
                console.print(f"[red]Trunk not found:[/red] {trunk_id}")
                return

        if grove_id:
            grove = session.query(Grove).filter(Grove.id == grove_id).first()
            if not grove:
                console.print(f"[red]Grove not found:[/red] {grove_id}")
                return

        br = Branch(
            title=title,
            trunk_id=trunk_id,
            grove_id=grove_id,
            description=description,
            done_when=done_when,
        )
        session.add(br)
        session.commit()
        console.print(f"[green]Created branch:[/green] {br.id}: {title}")


@branch.command()
@click.argument("branch_id", type=int)
def unlink(branch_id: int):
    """Remove beads link from a branch."""
    from grove.db import get_session
    from grove.models import Branch

    with get_session() as session:
        br = session.query(Branch).filter(Branch.id == branch_id).first()
        if not br:
            console.print(f"[red]Branch not found:[/red] {branch_id}")
            return

        if not br.beads_repo:
            console.print("[yellow]Branch not linked to beads[/yellow]")
            return

        old_path = br.beads_repo
        br.beads_repo = None
        session.commit()
        console.print(f"[green]Unlinked:[/green] {br.title} (was: {old_path})")


# =============================================================================
# BEADS INTEGRATION
# =============================================================================


@main.group()
def beads():
    """Beads integration commands for syncing with AI-native issue tracking."""
    pass


@beads.command()
@click.argument("branch_id", type=int)
@click.argument("bud_ids", nargs=-1, type=int)
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without creating issues")
def push(branch_id: int, bud_ids: tuple, dry_run: bool):
    """Push buds to beads in the linked repository.

    Exports buds from a branch as beads issues. If bud_ids are provided,
    only those buds are pushed. Otherwise, all seed/budding buds in the branch
    are pushed.

    Example: gv beads push 1
    Example: gv beads push 1 10 11 12
    """
    import os
    import subprocess
    from grove.db import get_session
    from grove.models import Branch, Bud

    with get_session() as session:
        br = session.query(Branch).filter(Branch.id == branch_id).first()
        if not br:
            console.print(f"[red]Branch not found:[/red] {branch_id}")
            return

        if not br.beads_repo:
            console.print("[red]Branch not linked to beads.[/red] Use 'gv branch link' first.")
            return

        # Verify beads path exists
        beads_path = br.beads_repo
        if not os.path.isdir(beads_path):
            console.print(f"[red]Beads directory not found:[/red] {beads_path}")
            return

        # Get buds to push
        if bud_ids:
            buds = session.query(Bud).filter(
                Bud.id.in_(bud_ids),
                Bud.branch_id == branch_id
            ).all()
            if len(buds) != len(bud_ids):
                found_ids = {b.id for b in buds}
                missing = [bid for bid in bud_ids if bid not in found_ids]
                console.print(f"[yellow]Warning: Buds not found in branch: {missing}[/yellow]")
        else:
            # Get all seed/budding buds in the branch
            buds = session.query(Bud).filter(
                Bud.branch_id == branch_id,
                Bud.status.in_(["seed", "budding"])
            ).all()

        if not buds:
            console.print("[dim]No buds to push[/dim]")
            return

        console.print(f"[cyan]Pushing {len(buds)} bud(s) to:[/cyan] {beads_path}")
        console.print()

        # Map priority strings to beads priority numbers
        priority_map = {
            "urgent": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
        }

        pushed = 0
        for bud in buds:
            # Build bd create command
            cmd = [
                "bd", "create",
                "--db", os.path.join(beads_path, "beads.db"),
                "--title", bud.title,
                "--priority", str(priority_map.get(bud.priority, 3)),
                "--type", "task",
            ]

            # Add description if present
            if bud.description:
                cmd.extend(["--description", bud.description])

            # Add notes about source
            source_note = f"Imported from grove bud #{bud.id}"
            if bud.context:
                source_note += f" (context: {bud.context})"
            cmd.extend(["--notes", source_note])

            if dry_run:
                console.print(f"  [dim]Would create:[/dim] {bud.title}")
                console.print(f"    [dim]cmd: {' '.join(cmd)}[/dim]")
            else:
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        cwd=os.path.dirname(beads_path)
                    )
                    if result.returncode == 0:
                        output = result.stdout.strip()
                        console.print(f"  [green]Created:[/green] {bud.title}")
                        if output:
                            console.print(f"    [dim]{output}[/dim]")
                        pushed += 1
                    else:
                        console.print(f"  [red]Failed:[/red] {bud.title}")
                        if result.stderr:
                            console.print(f"    [dim]{result.stderr}[/dim]")
                except Exception as e:
                    console.print(f"  [red]Error:[/red] {bud.title} - {e}")

        console.print()
        if dry_run:
            console.print(f"[dim]Dry run complete. Would push {len(buds)} bud(s).[/dim]")
        else:
            console.print(f"[green]Pushed {pushed}/{len(buds)} bud(s)[/green]")


@beads.command()
@click.argument("branch_id", type=int)
@click.option("--dry-run", is_flag=True, help="Show what would be imported without creating buds")
@click.option("--all", "import_all", is_flag=True, help="Import all beads, not just open ones")
def pull(branch_id: int, dry_run: bool, import_all: bool):
    """Pull beads from linked repository as buds.

    Imports open beads from the branch's linked beads repo as buds.
    Skips beads that have already been imported (matched by beads_id).

    Example: gv beads pull 1
    Example: gv beads pull 1 --all
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Branch, Bud
    from grove.beads import (
        resolve_beads_path,
        read_beads_jsonl,
        filter_open_beads,
        map_bead_status_to_bud_status,
        map_bead_priority_to_importance,
    )

    with get_session() as session:
        br = session.query(Branch).filter(Branch.id == branch_id).first()
        if not br:
            console.print(f"[red]Branch not found:[/red] {branch_id}")
            return

        if not br.beads_repo:
            console.print("[red]Branch not linked to beads.[/red] Use 'gv branch link' first.")
            return

        try:
            beads_dir = resolve_beads_path(br.beads_repo)
            all_beads = read_beads_jsonl(beads_dir)
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            return

        # Filter to open beads unless --all
        beads_to_import = all_beads if import_all else filter_open_beads(all_beads)

        if not beads_to_import:
            console.print("[dim]No beads to import[/dim]")
            return

        # Get existing beads_ids to avoid duplicates
        existing_bead_ids = set(
            b.beads_id for b in session.query(Bud.beads_id).filter(
                Bud.branch_id == branch_id,
                Bud.beads_id.isnot(None)
            ).all()
        )

        console.print(f"[cyan]Pulling from:[/cyan] {beads_dir}")
        console.print(f"[cyan]Found {len(beads_to_import)} bead(s), {len(existing_bead_ids)} already imported[/cyan]")
        console.print()

        imported = 0
        skipped = 0
        for bead in beads_to_import:
            if bead.id in existing_bead_ids:
                skipped += 1
                continue

            if dry_run:
                console.print(f"  [dim]Would import:[/dim] {bead.id}: {bead.title}")
            else:
                new_bud = Bud(
                    title=bead.title,
                    description=bead.description,
                    branch_id=branch_id,
                    status=map_bead_status_to_bud_status(bead.status),
                    priority=map_bead_priority_to_importance(bead.priority),
                    beads_id=bead.id,
                    beads_synced_at=datetime.utcnow(),
                )
                session.add(new_bud)
                console.print(f"  [green]Imported:[/green] {bead.id}: {bead.title}")
                imported += 1

        console.print()
        if dry_run:
            new_count = len(beads_to_import) - len(existing_bead_ids)
            console.print(f"[dim]Dry run complete. Would import {new_count} new bead(s), skip {skipped}.[/dim]")
        else:
            console.print(f"[green]Imported {imported} bud(s), skipped {skipped} existing[/green]")


@beads.command()
@click.argument("branch_id", type=int)
@click.option("--dry-run", is_flag=True, help="Show what would be synced without making changes")
def sync(branch_id: int, dry_run: bool):
    """Bidirectional sync between buds and beads.

    1. Pulls new beads as buds (like 'gv beads pull')
    2. Updates bud statuses from changed beads
    3. Reports buds not in beads (candidates for push)

    Example: gv beads sync 1
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Branch, Bud
    from grove.beads import (
        resolve_beads_path,
        read_beads_jsonl,
        filter_open_beads,
        map_bead_status_to_bud_status,
        map_bead_priority_to_importance,
    )

    with get_session() as session:
        br = session.query(Branch).filter(Branch.id == branch_id).first()
        if not br:
            console.print(f"[red]Branch not found:[/red] {branch_id}")
            return

        if not br.beads_repo:
            console.print("[red]Branch not linked to beads.[/red] Use 'gv branch link' first.")
            return

        try:
            beads_dir = resolve_beads_path(br.beads_repo)
            all_beads = read_beads_jsonl(beads_dir)
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            return

        beads_by_id = {b.id: b for b in all_beads}
        open_beads = filter_open_beads(all_beads)

        console.print(f"[cyan]Syncing branch {branch_id} with:[/cyan] {beads_dir}")
        console.print()

        # Phase 1: Pull new beads
        console.print("[bold]Phase 1: Pull new beads[/bold]")
        existing_buds = session.query(Bud).filter(
            Bud.branch_id == branch_id,
            Bud.beads_id.isnot(None)
        ).all()
        existing_bead_ids = {b.beads_id for b in existing_buds}

        pulled = 0
        for bead in open_beads:
            if bead.id not in existing_bead_ids:
                if dry_run:
                    console.print(f"  [dim]Would import:[/dim] {bead.id}: {bead.title}")
                else:
                    new_bud = Bud(
                        title=bead.title,
                        description=bead.description,
                        branch_id=branch_id,
                        status=map_bead_status_to_bud_status(bead.status),
                        priority=map_bead_priority_to_importance(bead.priority),
                        beads_id=bead.id,
                        beads_synced_at=datetime.utcnow(),
                    )
                    session.add(new_bud)
                    console.print(f"  [green]Imported:[/green] {bead.id}")
                pulled += 1

        if pulled == 0:
            console.print("  [dim]No new beads to pull[/dim]")
        console.print()

        # Phase 2: Update existing buds from beads
        console.print("[bold]Phase 2: Update buds from beads[/bold]")
        updated = 0
        for bud in existing_buds:
            if bud.beads_id in beads_by_id:
                bead = beads_by_id[bud.beads_id]
                new_status = map_bead_status_to_bud_status(bead.status)
                if bud.status != new_status:
                    if dry_run:
                        console.print(f"  [dim]Would update:[/dim] {bud.id}: {bud.status} → {new_status}")
                    else:
                        bud.status = new_status
                        bud.beads_synced_at = datetime.utcnow()
                        console.print(f"  [yellow]Updated:[/yellow] {bud.id}: {bud.status} → {new_status}")
                    updated += 1

        if updated == 0:
            console.print("  [dim]No status updates needed[/dim]")
        console.print()

        # Phase 3: Report buds without beads (candidates for push)
        console.print("[bold]Phase 3: Buds without beads (push candidates)[/bold]")
        unlinked_buds = session.query(Bud).filter(
            Bud.branch_id == branch_id,
            Bud.beads_id.is_(None),
            Bud.status.in_(["seed", "budding"])
        ).all()

        if unlinked_buds:
            for bud in unlinked_buds:
                console.print(f"  [dim]Not in beads:[/dim] {bud.id}: {bud.title}")
            console.print(f"\n  [dim]Run 'gv beads push {branch_id}' to export these[/dim]")
        else:
            console.print("  [dim]All buds are linked to beads[/dim]")

        console.print()
        console.print(f"[bold]Summary:[/bold] Pulled {pulled}, updated {updated}, {len(unlinked_buds)} unlinked")


@beads.command()
@click.argument("branch_id", type=int)
def status(branch_id: int):
    """Show beads sync status for a branch.

    Displays sync health: linked buds, unlinked buds, stale syncs.

    Example: gv beads status 1
    """
    from datetime import datetime, timedelta
    from grove.db import get_session
    from grove.models import Branch, Bud
    from grove.beads import resolve_beads_path, read_beads_jsonl, filter_open_beads

    with get_session() as session:
        br = session.query(Branch).filter(Branch.id == branch_id).first()
        if not br:
            console.print(f"[red]Branch not found:[/red] {branch_id}")
            return

        console.print(f"[bold]{br.title}[/bold]")
        console.print()

        if not br.beads_repo:
            console.print("[yellow]Not linked to beads[/yellow]")
            console.print(f"[dim]Run 'gv branch link {branch_id} /path/to/.beads' to link[/dim]")
            return

        console.print(f"[cyan]Beads repo:[/cyan] {br.beads_repo}")

        try:
            beads_dir = resolve_beads_path(br.beads_repo)
            all_beads = read_beads_jsonl(beads_dir)
            open_beads = filter_open_beads(all_beads)
            beads_by_id = {b.id: b for b in all_beads}
        except FileNotFoundError as e:
            console.print(f"[red]Error reading beads:[/red] {e}")
            return

        console.print(f"[cyan]Beads:[/cyan] {len(open_beads)} open / {len(all_beads)} total")
        console.print()

        # Get bud stats
        all_buds = session.query(Bud).filter(Bud.branch_id == branch_id).all()
        linked_buds = [b for b in all_buds if b.beads_id]
        unlinked_buds = [b for b in all_buds if not b.beads_id and b.status in ("seed", "budding")]

        # Check for stale syncs (>24h old)
        stale_threshold = datetime.utcnow() - timedelta(hours=24)
        stale_buds = [b for b in linked_buds if b.beads_synced_at and b.beads_synced_at < stale_threshold]

        # Check for orphaned links (bud points to bead that no longer exists)
        orphaned_buds = [b for b in linked_buds if b.beads_id not in beads_by_id]

        # Check for unimported beads
        imported_bead_ids = {b.beads_id for b in linked_buds}
        unimported_beads = [b for b in open_beads if b.id not in imported_bead_ids]

        console.print("[bold]Buds[/bold]")
        console.print(f"  Total: {len(all_buds)}")
        console.print(f"  Linked to beads: {len(linked_buds)}")
        console.print(f"  Unlinked (active): {len(unlinked_buds)}")
        console.print()

        console.print("[bold]Sync Health[/bold]")
        if stale_buds:
            console.print(f"  [yellow]Stale syncs (>24h):[/yellow] {len(stale_buds)}")
        else:
            console.print("  [green]All syncs fresh[/green]")

        if orphaned_buds:
            console.print(f"  [red]Orphaned links:[/red] {len(orphaned_buds)}")
            for b in orphaned_buds[:3]:
                console.print(f"    {b.id}: {b.beads_id} (bead not found)")
        else:
            console.print("  [green]No orphaned links[/green]")

        if unimported_beads:
            console.print(f"  [yellow]Unimported beads:[/yellow] {len(unimported_beads)}")
            for b in unimported_beads[:3]:
                console.print(f"    {b.id}: {b.title[:40]}")
            if len(unimported_beads) > 3:
                console.print(f"    ... and {len(unimported_beads) - 3} more")
        else:
            console.print("  [green]All open beads imported[/green]")

        console.print()
        if unlinked_buds or unimported_beads:
            console.print(f"[dim]Run 'gv beads sync {branch_id}' to synchronize[/dim]")


# =============================================================================
# OVERVIEW
# =============================================================================


@main.command()
def overview():
    """Show full hierarchy tree with counts and progress.

    Displays all groves, trunks, branches, and bud counts.

    Example: gv overview
    """
    from grove.db import get_session
    from grove.models import Grove, Trunk, Branch, Bud

    with get_session() as session:
        # Get all groves
        groves = session.query(Grove).order_by(Grove.name).all()

        # Get orphan trunks (no grove)
        orphan_trunks = session.query(Trunk).filter(
            Trunk.grove_id.is_(None)
        ).order_by(Trunk.title).all()

        # Get orphan branches (no trunk)
        orphan_branches = session.query(Branch).filter(
            Branch.trunk_id.is_(None)
        ).order_by(Branch.title).all()

        # Get orphan buds (no branch)
        orphan_buds = session.query(Bud).filter(
            Bud.branch_id.is_(None),
            Bud.status != "bloomed"
        ).all()

        console.print()
        console.print("[bold]Grove Overview[/bold]")
        console.print("=" * 40)

        for grove in groves:
            icon = grove.icon or "🌳"
            trunks = session.query(Trunk).filter(Trunk.grove_id == grove.id).all()

            # Count all buds under this grove
            grove_bud_count = 0
            grove_bloomed_count = 0

            for trunk in trunks:
                branches = session.query(Branch).filter(Branch.trunk_id == trunk.id).all()
                for br in branches:
                    buds = session.query(Bud).filter(Bud.branch_id == br.id).all()
                    grove_bud_count += len(buds)
                    grove_bloomed_count += len([b for b in buds if b.status == "bloomed"])

            progress = f"{grove_bloomed_count}/{grove_bud_count}" if grove_bud_count > 0 else "0/0"
            console.print()
            console.print(f"[bold green]{icon} {grove.name}[/bold green] [{progress}]")

            for trunk in trunks:
                branches = session.query(Branch).filter(Branch.trunk_id == trunk.id).all()

                # Count buds for this trunk
                trunk_bud_count = 0
                trunk_bloomed_count = 0
                for br in branches:
                    buds = session.query(Bud).filter(Bud.branch_id == br.id).all()
                    trunk_bud_count += len(buds)
                    trunk_bloomed_count += len([b for b in buds if b.status == "bloomed"])

                progress = f"{trunk_bloomed_count}/{trunk_bud_count}" if trunk_bud_count > 0 else "0/0"
                status_icon = "○" if trunk.status == "active" else "●"
                console.print(f"  {status_icon} [magenta]{trunk.title}[/magenta] [{progress}]")

                for br in branches:
                    buds = session.query(Bud).filter(Bud.branch_id == br.id).all()
                    bloomed_count = len([b for b in buds if b.status == "bloomed"])
                    total_count = len(buds)
                    progress = f"{bloomed_count}/{total_count}" if total_count > 0 else "0/0"
                    status_icon = "○" if br.status == "active" else "●"
                    console.print(f"    {status_icon} [yellow]{br.title}[/yellow] [{progress}]")

        # Show orphans
        if orphan_trunks:
            console.print()
            console.print("[bold dim]Unrooted Trunks[/bold dim]")
            for trunk in orphan_trunks:
                branches = session.query(Branch).filter(Branch.trunk_id == trunk.id).all()
                trunk_bud_count = 0
                trunk_bloomed_count = 0
                for br in branches:
                    buds = session.query(Bud).filter(Bud.branch_id == br.id).all()
                    trunk_bud_count += len(buds)
                    trunk_bloomed_count += len([b for b in buds if b.status == "bloomed"])
                progress = f"{trunk_bloomed_count}/{trunk_bud_count}" if trunk_bud_count > 0 else "0/0"
                console.print(f"  ○ [magenta]{trunk.title}[/magenta] [{progress}]")

        if orphan_branches:
            console.print()
            console.print("[bold dim]Floating Branches[/bold dim]")
            for br in orphan_branches:
                buds = session.query(Bud).filter(Bud.branch_id == br.id).all()
                bloomed_count = len([b for b in buds if b.status == "bloomed"])
                total_count = len(buds)
                progress = f"{bloomed_count}/{total_count}" if total_count > 0 else "0/0"
                console.print(f"  ○ [yellow]{br.title}[/yellow] [{progress}]")

        if orphan_buds:
            console.print()
            console.print(f"[bold dim]Loose Buds[/bold dim] [{len(orphan_buds)} items]")
            for bud in orphan_buds[:5]:
                console.print(f"  • [dim]{bud.title}[/dim]")
            if len(orphan_buds) > 5:
                console.print(f"  [dim]... and {len(orphan_buds) - 5} more[/dim]")

        # Summary stats
        total_buds = session.query(Bud).count()
        bloomed_buds = session.query(Bud).filter(Bud.status == "bloomed").count()
        budding_buds = session.query(Bud).filter(Bud.status == "budding").count()
        seed_buds = session.query(Bud).filter(Bud.status == "seed").count()

        console.print()
        console.print("=" * 40)
        console.print(f"[bold]Total:[/bold] {total_buds} buds | "
                      f"[green]{bloomed_buds} bloomed[/green] | "
                      f"[cyan]{budding_buds} budding[/cyan] | "
                      f"[yellow]{seed_buds} seeds[/yellow]")
        console.print()


# =============================================================================
# REVIEW
# =============================================================================


@main.command()
def review():
    """Guided weekly review flow.

    Walks through a structured review:
    1. Process seeds (inbox)
    2. Review stale buds
    3. Check blocked work
    4. Review branch progress
    5. Celebrate blooms

    Example: gv review
    """
    from datetime import datetime, timedelta
    from grove.db import get_session
    from grove.models import Bud, Branch, Grove

    with get_session() as session:
        console.print()
        console.print("[bold magenta]═══ Weekly Review ═══[/bold magenta]")
        console.print()

        # Step 1: Seeds
        seed_buds = session.query(Bud).filter(Bud.status == "seed").all()
        console.print("[bold]1. Seeds (Inbox)[/bold]")
        if seed_buds:
            console.print(f"   [yellow]{len(seed_buds)} seed(s) need planting:[/yellow]")
            for bud in seed_buds[:5]:
                console.print(f"   • {bud.id}: {bud.title}")
            if len(seed_buds) > 5:
                console.print(f"   ... and {len(seed_buds) - 5} more")
            console.print()
            console.print("   [dim]Run 'gv seeds' to process these[/dim]")
        else:
            console.print("   [green]✓ No seeds waiting[/green]")
        console.print()

        # Step 2: Stale buds (not updated in 7+ days)
        stale_threshold = datetime.utcnow() - timedelta(days=7)
        stale_buds = session.query(Bud).filter(
            Bud.status == "budding",
            Bud.updated_at < stale_threshold
        ).all()

        console.print("[bold]2. Stale Buds[/bold]")
        if stale_buds:
            console.print(f"   [yellow]{len(stale_buds)} bud(s) haven't grown in 7+ days:[/yellow]")
            for bud in stale_buds[:5]:
                days_old = (datetime.utcnow() - bud.updated_at).days
                console.print(f"   • {bud.id}: {bud.title} ({days_old}d)")
            if len(stale_buds) > 5:
                console.print(f"   ... and {len(stale_buds) - 5} more")
            console.print()
            console.print("   [dim]Consider: still growing? blocked? needs breakdown?[/dim]")
        else:
            console.print("   [green]✓ No stale buds[/green]")
        console.print()

        # Step 3: Blocked buds
        from grove.models import BudDependency
        blocked_count = session.query(Bud).join(
            BudDependency, Bud.id == BudDependency.bud_id
        ).filter(
            Bud.status == "budding",
            BudDependency.dependency_type == "blocks"
        ).distinct().count()

        console.print("[bold]3. Blocked Buds[/bold]")
        if blocked_count:
            console.print(f"   [yellow]{blocked_count} bud(s) are blocked[/yellow]")
            console.print("   [dim]Run 'gv blocked' to see details[/dim]")
        else:
            console.print("   [green]✓ No blocked buds[/green]")
        console.print()

        # Step 4: Branch progress
        console.print("[bold]4. Branch Progress[/bold]")
        branches = session.query(Branch).filter(Branch.status == "active").all()
        if branches:
            for br in branches[:5]:
                buds = session.query(Bud).filter(Bud.branch_id == br.id).all()
                total = len(buds)
                bloomed = len([b for b in buds if b.status == "bloomed"])
                budding = len([b for b in buds if b.status == "budding"])
                if total > 0:
                    pct = int(bloomed / total * 100)
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    console.print(f"   {bar} {pct}% {br.title}")
                    console.print(f"   [dim]{bloomed} bloomed, {budding} budding, {total - bloomed - budding} other[/dim]")
                else:
                    console.print(f"   [dim]{br.title} (no buds)[/dim]")
            if len(branches) > 5:
                console.print(f"   ... and {len(branches) - 5} more branches")
        else:
            console.print("   [dim]No active branches[/dim]")
        console.print()

        # Step 5: Recent blooms
        week_ago = datetime.utcnow() - timedelta(days=7)
        bloomed = session.query(Bud).filter(
            Bud.status == "bloomed",
            Bud.completed_at >= week_ago
        ).all()

        console.print("[bold]5. This Week's Blooms[/bold]")
        if bloomed:
            console.print(f"   [green]🌸 {len(bloomed)} bud(s) bloomed![/green]")
            for bud in bloomed[:5]:
                console.print(f"   ✓ {bud.title}")
            if len(bloomed) > 5:
                console.print(f"   ... and {len(bloomed) - 5} more")
        else:
            console.print("   [dim]No blooms this week[/dim]")
        console.print()

        console.print("[bold magenta]═══ Review Complete ═══[/bold magenta]")
        console.print()


# =============================================================================
# HABIT MANAGEMENT
# =============================================================================


@main.group()
def habit():
    """Habit tracking commands."""
    pass


@habit.command(name="new")
@click.argument("name")
@click.option("--frequency", "-f", default="daily", type=click.Choice(["daily", "weekly", "3x_week"]))
@click.option("--grove", "-g", "grove_id", type=int, help="Link to a grove")
def habit_new(name: str, frequency: str, grove_id: int | None):
    """Create a new habit to track.

    Example: gv habit new "Morning meditation" -f daily
    Example: gv habit new "Gym session" -f 3x_week --grove 1
    """
    from grove.db import get_session
    from grove.models import Habit, Grove

    with get_session() as session:
        if grove_id:
            grove = session.query(Grove).filter(Grove.id == grove_id).first()
            if not grove:
                console.print(f"[red]Grove not found:[/red] {grove_id}")
                return

        habit = Habit(title=name, frequency=frequency, grove_id=grove_id)
        session.add(habit)
        session.flush()
        console.print(f"[green]Created habit:[/green] {habit.id}: {name} ({frequency})")


@habit.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="Include inactive habits")
def habit_list(show_all: bool):
    """List all habits.

    Example: gv habit list
    Example: gv habit list --all
    """
    from grove.db import get_session
    from grove.models import Habit, HabitLog
    from datetime import datetime, timedelta

    with get_session() as session:
        query = session.query(Habit)
        if not show_all:
            query = query.filter(Habit.is_active == True)
        habits = query.order_by(Habit.title).all()

        if not habits:
            console.print("[dim]No habits found[/dim]")
            return

        today = datetime.utcnow().date()
        week_ago = datetime.utcnow() - timedelta(days=7)

        console.print("[bold]Habits:[/bold]")
        for habit in habits:
            # Count completions this week
            week_count = session.query(HabitLog).filter(
                HabitLog.habit_id == habit.id,
                HabitLog.completed_at >= week_ago
            ).count()

            # Check if done today
            today_done = session.query(HabitLog).filter(
                HabitLog.habit_id == habit.id,
                HabitLog.completed_at >= datetime.combine(today, datetime.min.time())
            ).first()

            status = "[green]✓[/green]" if today_done else "[dim]○[/dim]"
            freq_label = {"daily": "d", "weekly": "w", "3x_week": "3x"}[habit.frequency]
            console.print(f"{status} {habit.id}: {habit.title} ({freq_label}) [{week_count}/7d]")


@habit.command(name="done")
@click.argument("habit_id", type=int)
@click.option("--notes", "-n", help="Optional notes")
def habit_done(habit_id: int, notes: str | None):
    """Log a habit completion.

    Example: gv habit done 1
    Example: gv habit done 1 -n "20 minutes"
    """
    from grove.db import get_session
    from grove.models import Habit, HabitLog

    with get_session() as session:
        habit = session.query(Habit).filter(Habit.id == habit_id).first()
        if not habit:
            console.print(f"[red]Habit not found:[/red] {habit_id}")
            return

        log = HabitLog(habit_id=habit_id, notes=notes)
        session.add(log)
        console.print(f"[green]✓[/green] Logged: {habit.title}")


@habit.command(name="stats")
@click.argument("habit_id", type=int)
def habit_stats(habit_id: int):
    """Show statistics for a habit.

    Example: gv habit stats 1
    """
    from datetime import datetime, timedelta, timezone
    from grove.db import get_session
    from grove.models import Habit, HabitLog

    with get_session() as session:
        habit = session.query(Habit).filter(Habit.id == habit_id).first()
        if not habit:
            console.print(f"[red]Habit not found:[/red] {habit_id}")
            return

        console.print(f"[bold]{habit.title}[/bold] ({habit.frequency})")
        console.print()

        # Get all logs
        logs = session.query(HabitLog).filter(
            HabitLog.habit_id == habit_id
        ).order_by(HabitLog.completed_at.desc()).all()

        total = len(logs)

        # Use timezone-aware datetime for comparisons
        now = datetime.now(timezone.utc)

        # This week
        week_ago = now - timedelta(days=7)
        this_week = len([l for l in logs if l.completed_at and l.completed_at >= week_ago])

        # This month
        month_ago = now - timedelta(days=30)
        this_month = len([l for l in logs if l.completed_at and l.completed_at >= month_ago])

        # Current streak
        streak = 0
        if logs:
            today = datetime.utcnow().date()
            check_date = today
            log_dates = {l.completed_at.date() for l in logs}

            while check_date in log_dates:
                streak += 1
                check_date -= timedelta(days=1)

        console.print(f"[cyan]Total completions:[/cyan] {total}")
        console.print(f"[cyan]This week:[/cyan] {this_week}")
        console.print(f"[cyan]This month:[/cyan] {this_month}")
        console.print(f"[cyan]Current streak:[/cyan] {streak} day(s)")

        # Last 7 days visualization
        console.print()
        console.print("[bold]Last 7 days:[/bold]")
        today = datetime.utcnow().date()
        log_dates = {l.completed_at.date() for l in logs}
        days = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            days.append("█" if d in log_dates else "░")
        console.print(f"  {''.join(days)}")
        console.print(f"  [dim]{''.join(['MTWTFSS'[(today - timedelta(days=6-i)).weekday()] for i in range(7)])}[/dim]")


@habit.command(name="pause")
@click.argument("habit_id", type=int)
def habit_pause(habit_id: int):
    """Pause a habit (mark inactive).

    Example: gv habit pause 1
    """
    from grove.db import get_session
    from grove.models import Habit

    with get_session() as session:
        habit = session.query(Habit).filter(Habit.id == habit_id).first()
        if not habit:
            console.print(f"[red]Habit not found:[/red] {habit_id}")
            return

        habit.is_active = False
        console.print(f"[yellow]Paused:[/yellow] {habit.title}")


@habit.command(name="resume")
@click.argument("habit_id", type=int)
def habit_resume(habit_id: int):
    """Resume a paused habit.

    Example: gv habit resume 1
    """
    from grove.db import get_session
    from grove.models import Habit

    with get_session() as session:
        habit = session.query(Habit).filter(Habit.id == habit_id).first()
        if not habit:
            console.print(f"[red]Habit not found:[/red] {habit_id}")
            return

        habit.is_active = True
        console.print(f"[green]Resumed:[/green] {habit.title}")


# =============================================================================
# TRUNK (Initiative) MANAGEMENT
# =============================================================================


@main.group()
def trunk():
    """Manage trunks (strategic initiatives)."""
    pass


@trunk.command(name="new")
@click.argument("title")
@click.option("--grove", "-g", "grove_id", type=int, help="Link to a grove")
@click.option("--description", "-d", help="Trunk description")
@click.option("--target", "-t", help="Target date (YYYY-MM-DD)")
@click.option("--priority", "-p", type=click.Choice(["high", "medium", "low"]), default="medium", help="Priority level")
def trunk_new(title: str, grove_id: int | None, description: str | None, target: str | None, priority: str):
    """Create a new trunk (strategic initiative).

    Example: gv trunk new "Ship personal projects" --grove 1
    Example: gv trunk new "Learn Rust" -g 2 -d "Deep dive into systems programming" -t 2025-06-01
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Trunk, Grove

    with get_session() as session:
        # Validate grove if provided
        if grove_id:
            grove = session.query(Grove).filter(Grove.id == grove_id).first()
            if not grove:
                console.print(f"[red]Grove not found:[/red] {grove_id}")
                return

        # Parse target date if provided
        target_date = None
        if target:
            try:
                target_date = datetime.strptime(target, "%Y-%m-%d").date()
            except ValueError:
                console.print(f"[red]Invalid date format:[/red] {target} (use YYYY-MM-DD)")
                return

        trunk = Trunk(
            title=title,
            grove_id=grove_id,
            description=description,
            target_date=target_date,
            priority=priority,
            status="active",
        )
        session.add(trunk)
        session.commit()

        grove_info = f" (grove: {grove.name})" if grove_id else ""
        console.print(f"[green]Created trunk:[/green] {trunk.id}: {title}{grove_info}")


@trunk.command(name="list")
@click.option("--grove", "-g", "grove_id", type=int, help="Filter by grove ID")
@click.option("--all", "show_all", is_flag=True, help="Include completed trunks")
def trunk_list(grove_id: int | None, show_all: bool):
    """List trunks.

    Example: gv trunk list
    Example: gv trunk list --grove 1
    Example: gv trunk list --all
    """
    from grove.db import get_session
    from grove.models import Trunk, Grove

    with get_session() as session:
        query = session.query(Trunk)

        if grove_id:
            grove = session.query(Grove).filter(Grove.id == grove_id).first()
            if not grove:
                console.print(f"[red]Grove not found:[/red] {grove_id}")
                return
            query = query.filter(Trunk.grove_id == grove_id)
            console.print(f"[cyan]Trunks in {grove.name}:[/cyan]")
        else:
            console.print("[cyan]All trunks:[/cyan]")

        if not show_all:
            query = query.filter(Trunk.status != "completed")

        trunks = query.order_by(Trunk.priority, Trunk.title).all()

        if not trunks:
            console.print("[dim]No trunks found[/dim]")
            return

        console.print()
        for trunk in trunks:
            status_icon = "●" if trunk.status == "completed" else "○"
            priority_color = {"high": "red", "medium": "yellow", "low": "dim"}.get(trunk.priority, "white")

            # Get grove name if linked
            grove_label = ""
            if trunk.grove_id:
                grove = session.query(Grove).filter(Grove.id == trunk.grove_id).first()
                if grove:
                    icon = grove.icon or "🌳"
                    grove_label = f" [{icon} {grove.name}]"

            # Target date info
            target_label = ""
            if trunk.target_date:
                target_label = f" (target: {trunk.target_date.strftime('%Y-%m-%d')})"

            console.print(f"  {status_icon} [{priority_color}]{trunk.id}[/{priority_color}]: {trunk.title}[dim]{grove_label}{target_label}[/dim]")


@trunk.command(name="show")
@click.argument("trunk_id", type=int)
def trunk_show(trunk_id: int):
    """Show trunk details with branches/buds count.

    Example: gv trunk show 1
    """
    from grove.db import get_session
    from grove.models import Trunk, Grove, Branch, Bud

    with get_session() as session:
        trunk = session.query(Trunk).filter(Trunk.id == trunk_id).first()
        if not trunk:
            console.print(f"[red]Trunk not found:[/red] {trunk_id}")
            return

        console.print()
        console.print(f"[bold magenta]Trunk:[/bold magenta] {trunk.title}")
        console.print(f"  [dim]id: {trunk.id} | status: {trunk.status} | priority: {trunk.priority}[/dim]")

        if trunk.description:
            console.print(f"  [dim]{trunk.description}[/dim]")

        if trunk.target_date:
            console.print(f"  [dim]target: {trunk.target_date.strftime('%Y-%m-%d')}[/dim]")

        if trunk.labels:
            console.print(f"  [dim]labels: {', '.join(trunk.labels)}[/dim]")

        # Show linked grove
        if trunk.grove_id:
            grove = session.query(Grove).filter(Grove.id == trunk.grove_id).first()
            if grove:
                icon = grove.icon or "🌳"
                console.print()
                console.print(f"  [bold green]Grove:[/bold green] {icon} {grove.name}")

        # Count branches under this trunk
        branch_count = session.query(Branch).filter(Branch.trunk_id == trunk.id).count()
        branch_done = session.query(Branch).filter(
            Branch.trunk_id == trunk.id,
            Branch.status == "completed"
        ).count()

        # Count buds under this trunk (direct + via branches)
        direct_bud_count = session.query(Bud).filter(Bud.trunk_id == trunk.id).count()
        direct_bud_bloomed = session.query(Bud).filter(
            Bud.trunk_id == trunk.id,
            Bud.status == "bloomed"
        ).count()

        # Buds via branches
        branch_ids = [b.id for b in session.query(Branch.id).filter(Branch.trunk_id == trunk.id).all()]
        branch_bud_count = session.query(Bud).filter(Bud.branch_id.in_(branch_ids)).count() if branch_ids else 0
        branch_bud_bloomed = session.query(Bud).filter(
            Bud.branch_id.in_(branch_ids),
            Bud.status == "bloomed"
        ).count() if branch_ids else 0

        total_buds = direct_bud_count + branch_bud_count
        total_bloomed = direct_bud_bloomed + branch_bud_bloomed

        console.print()
        console.print(f"  [cyan]Branches:[/cyan] {branch_done}/{branch_count}")
        console.print(f"  [cyan]Buds:[/cyan] {total_bloomed}/{total_buds} ({direct_bud_count} direct, {branch_bud_count} via branches)")

        # List branches if any
        if branch_count > 0:
            console.print()
            console.print("  [bold]Branches:[/bold]")
            branches = session.query(Branch).filter(Branch.trunk_id == trunk.id).order_by(Branch.title).all()
            for br in branches[:10]:
                status_icon = "●" if br.status == "completed" else "○"
                console.print(f"    {status_icon} {br.id}: {br.title}")
            if branch_count > 10:
                console.print(f"    [dim]... and {branch_count - 10} more[/dim]")

        console.print()


@trunk.command(name="done")
@click.argument("trunk_id", type=int)
def trunk_done(trunk_id: int):
    """Mark a trunk as completed.

    Example: gv trunk done 1
    """
    from grove.db import get_session
    from grove.models import Trunk

    with get_session() as session:
        trunk = session.query(Trunk).filter(Trunk.id == trunk_id).first()
        if not trunk:
            console.print(f"[red]Trunk not found:[/red] {trunk_id}")
            return

        if trunk.status == "completed":
            console.print(f"[yellow]Trunk already completed:[/yellow] {trunk.title}")
            return

        trunk.status = "completed"
        session.commit()
        console.print(f"[green]Completed:[/green] {trunk.title}")


@trunk.command(name="link")
@click.argument("trunk_id", type=int)
@click.option("--grove", "-g", "grove_id", type=int, required=True, help="Grove ID to link to")
def trunk_link(trunk_id: int, grove_id: int):
    """Link a trunk to a grove.

    Example: gv trunk link 1 --grove 2
    """
    from grove.db import get_session
    from grove.models import Trunk, Grove

    with get_session() as session:
        trunk = session.query(Trunk).filter(Trunk.id == trunk_id).first()
        if not trunk:
            console.print(f"[red]Trunk not found:[/red] {trunk_id}")
            return

        grove = session.query(Grove).filter(Grove.id == grove_id).first()
        if not grove:
            console.print(f"[red]Grove not found:[/red] {grove_id}")
            return

        old_grove_id = trunk.grove_id
        trunk.grove_id = grove_id
        session.commit()

        if old_grove_id:
            old_grove = session.query(Grove).filter(Grove.id == old_grove_id).first()
            old_name = old_grove.name if old_grove else f"id:{old_grove_id}"
            console.print(f"[green]Relinked:[/green] {trunk.title}")
            console.print(f"  [dim]{old_name} -> {grove.name}[/dim]")
        else:
            icon = grove.icon or "🌳"
            console.print(f"[green]Linked:[/green] {trunk.title} -> {icon} {grove.name}")


# =============================================================================
# GROVE (Area) MANAGEMENT
# =============================================================================


@main.group()
def grove():
    """Manage groves (life areas like Health, Coding, etc.)."""
    pass


@grove.command(name="new")
@click.argument("name")
@click.option("--icon", "-i", help="Emoji icon for the grove (e.g., '🌳')")
@click.option("--description", "-d", help="Description of the grove")
@click.option("--color", "-c", help="Hex color code (e.g., '#FF5733')")
def grove_new(name: str, icon: str | None, description: str | None, color: str | None):
    """Create a new grove.

    Example: gv grove new "Health" --icon "🏃" --description "Physical and mental wellness"
    Example: gv grove new "Coding" -i "💻"
    """
    from grove.db import get_session
    from grove.models import Grove

    with get_session() as session:
        # Check if grove with same name already exists
        existing = session.query(Grove).filter(Grove.name == name).first()
        if existing:
            console.print(f"[red]Grove already exists:[/red] {name} (id: {existing.id})")
            return

        # Get next sort order
        max_order = session.query(Grove.sort_order).order_by(Grove.sort_order.desc()).first()
        next_order = (max_order[0] + 1) if max_order else 0

        g = Grove(
            name=name,
            icon=icon,
            description=description,
            color=color,
            sort_order=next_order,
        )
        session.add(g)
        session.flush()

        icon_display = f"{icon} " if icon else ""
        console.print(f"[green]Created grove:[/green] {g.id}: {icon_display}{name}")


@grove.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="Include inactive groves")
def grove_list(show_all: bool):
    """List all groves.

    Example: gv grove list
    Example: gv grove list --all
    """
    from grove.db import get_session
    from grove.models import Grove, Trunk, Bud

    with get_session() as session:
        query = session.query(Grove)
        if not show_all:
            query = query.filter(Grove.is_active == True)
        groves = query.order_by(Grove.sort_order, Grove.name).all()

        if not groves:
            console.print("[dim]No groves found[/dim]")
            return

        console.print("[bold]Groves:[/bold]")
        for g in groves:
            icon = g.icon or "🌳"
            status = "" if g.is_active else " [dim](archived)[/dim]"

            # Count trunks
            trunk_count = session.query(Trunk).filter(Trunk.grove_id == g.id).count()

            # Count buds (direct and via trunks/branches)
            direct_buds = session.query(Bud).filter(Bud.grove_id == g.id).count()

            console.print(f"  {g.id}: {icon} {g.name}{status} [{trunk_count} trunks, {direct_buds} direct buds]")
            if g.description:
                console.print(f"     [dim]{g.description}[/dim]")


@grove.command(name="show")
@click.argument("grove_id", type=int)
def grove_show(grove_id: int):
    """Show grove details with trunks and bud counts.

    Example: gv grove show 1
    """
    from grove.db import get_session
    from grove.models import Grove, Trunk, Branch, Bud

    with get_session() as session:
        g = session.query(Grove).filter(Grove.id == grove_id).first()
        if not g:
            console.print(f"[red]Grove not found:[/red] {grove_id}")
            return

        icon = g.icon or "🌳"
        status = "[green]active[/green]" if g.is_active else "[yellow]archived[/yellow]"

        console.print()
        console.print(f"[bold green]{icon} {g.name}[/bold green]")
        console.print(f"  [dim]id: {g.id} | status: {status}[/dim]")
        if g.description:
            console.print(f"  [dim]{g.description}[/dim]")
        if g.color:
            console.print(f"  [dim]color: {g.color}[/dim]")
        console.print()

        # Get trunks in this grove
        trunks = session.query(Trunk).filter(Trunk.grove_id == g.id).all()

        # Count buds at each level
        direct_buds = session.query(Bud).filter(Bud.grove_id == g.id).count()
        direct_bloomed = session.query(Bud).filter(Bud.grove_id == g.id, Bud.status == "bloomed").count()

        # Buds via trunks and branches
        total_buds = direct_buds
        total_bloomed = direct_bloomed
        for trunk in trunks:
            # Buds directly on trunk
            trunk_buds = session.query(Bud).filter(Bud.trunk_id == trunk.id).count()
            trunk_bloomed = session.query(Bud).filter(Bud.trunk_id == trunk.id, Bud.status == "bloomed").count()
            total_buds += trunk_buds
            total_bloomed += trunk_bloomed

            # Buds via branches
            branches = session.query(Branch).filter(Branch.trunk_id == trunk.id).all()
            for br in branches:
                br_buds = session.query(Bud).filter(Bud.branch_id == br.id).count()
                br_bloomed = session.query(Bud).filter(Bud.branch_id == br.id, Bud.status == "bloomed").count()
                total_buds += br_buds
                total_bloomed += br_bloomed

        # Direct branches under grove
        direct_branches = session.query(Branch).filter(Branch.grove_id == g.id).all()
        for br in direct_branches:
            br_buds = session.query(Bud).filter(Bud.branch_id == br.id).count()
            br_bloomed = session.query(Bud).filter(Bud.branch_id == br.id, Bud.status == "bloomed").count()
            total_buds += br_buds
            total_bloomed += br_bloomed

        console.print("[bold]Statistics[/bold]")
        console.print(f"  Trunks: {len(trunks)}")
        console.print(f"  Direct branches: {len(direct_branches)}")
        console.print(f"  Total buds: {total_bloomed}/{total_buds} bloomed")
        console.print()

        if trunks:
            console.print("[bold]Trunks[/bold]")
            for trunk in trunks:
                status_icon = "○" if trunk.status == "active" else "●"
                console.print(f"  {status_icon} {trunk.id}: {trunk.title}")
            console.print()


@grove.command(name="archive")
@click.argument("grove_id", type=int)
def grove_archive(grove_id: int):
    """Archive a grove (soft delete).

    Archived groves won't show in 'gv grove list' but can be viewed with --all.
    This does NOT delete trunks, branches, or buds under the grove.

    Example: gv grove archive 1
    """
    from grove.db import get_session
    from grove.models import Grove

    with get_session() as session:
        g = session.query(Grove).filter(Grove.id == grove_id).first()
        if not g:
            console.print(f"[red]Grove not found:[/red] {grove_id}")
            return

        if not g.is_active:
            console.print(f"[yellow]Grove already archived:[/yellow] {g.name}")
            return

        g.is_active = False
        icon = g.icon or "🌳"
        console.print(f"[yellow]Archived:[/yellow] {icon} {g.name}")
        console.print("[dim]Run 'gv grove list --all' to see archived groves[/dim]")


# =============================================================================
# ALIASES for backward compatibility and convenience
# =============================================================================


# Keep 'done' as alias for 'bloom' for muscle memory
@main.command(name="done")
@click.argument("bud_id", type=int)
def done_alias(bud_id: int):
    """Alias for 'bloom' - mark a bud as complete.

    Example: gv done 1
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        bud = session.query(Bud).filter(Bud.id == bud_id).first()
        if not bud:
            console.print(f"[red]Bud not found:[/red] {bud_id}")
            return
        bud.status = "bloomed"
        bud.completed_at = datetime.utcnow()
        session.commit()
        console.print(f"[green]🌸 Bloomed:[/green] {bud.title}")


# Keep 'inbox' as alias for 'seeds' for muscle memory
@main.command(name="inbox")
def inbox_alias():
    """Alias for 'seeds' - show unprocessed items.

    Example: gv inbox
    """
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        buds = session.query(Bud).filter(Bud.status == "seed").all()
        if not buds:
            console.print("[dim]No seeds to process[/dim]")
            return
        console.print("[bold]Seeds (unprocessed):[/bold]")
        for bud in buds:
            console.print(f"  {bud.id}: {bud.title}")


# Keep 'now' as alias for 'pulse' for muscle memory
@main.command(name="now")
def now_alias():
    """Alias for 'pulse' - show actionable, unblocked buds.

    Example: gv now
    """
    from sqlalchemy import and_, select
    from grove.db import get_session
    from grove.models import Bud, BudDependency

    with get_session() as session:
        blocked_subq = select(BudDependency.bud_id).join(
            Bud, BudDependency.depends_on_id == Bud.id
        ).where(
            and_(
                BudDependency.dependency_type == "blocks",
                Bud.status != "bloomed"
            )
        ).scalar_subquery()

        buds = session.query(Bud).filter(
            Bud.status == "budding",
            ~Bud.id.in_(blocked_subq)
        ).all()

        if not buds:
            console.print("[dim]Nothing ready to work on right now[/dim]")
            return
        console.print("[bold]Ready to bloom:[/bold]")
        for bud in buds:
            console.print(f"  {bud.id}: {bud.title}")


if __name__ == "__main__":
    main()
