"""CLI entrypoint for Grove - botanical task management.

Naming scheme:
- Groves: Life domains
- Trunks: Strategic initiatives
- Stems: Projects
- Buds: Tasks (status: seed → dormant → budding → bloomed/mulch)
- Fruits: Key results (OKRs)
- Seeds: Unprocessed buds (gv seeds command)
- Pulse: Check what's actionable (gv pulse command)
"""

import click
from rich.console import Console

console = Console()


def parse_item_ref(ref: str) -> tuple[str, int]:
    """Parse item reference like 'b:45' or 's:12' into (item_type, item_id).

    Prefixes:
      g:  -> grove
      t:  -> trunk
      s:  -> stem
      b:  -> bud

    Raises click.BadParameter if invalid format.
    """
    prefixes = {
        'g': 'grove',
        't': 'trunk',
        's': 'stem',
        'b': 'bud',
    }

    if ':' not in ref:
        raise click.BadParameter(
            f"Invalid format '{ref}'. Use prefix:id (e.g., b:45, s:12, t:16, g:1)"
        )

    parts = ref.split(':', 1)
    prefix = parts[0].lower()

    if prefix not in prefixes:
        raise click.BadParameter(
            f"Unknown prefix '{prefix}'. Use: g (grove), t (trunk), s (stem), b (bud)"
        )

    try:
        item_id = int(parts[1])
    except ValueError:
        raise click.BadParameter(f"Invalid ID '{parts[1]}'. Must be a number.")

    return prefixes[prefix], item_id


def get_item_by_ref(session, item_type: str, item_id: int):
    """Get an item by type and ID. Returns (item, model_class) or (None, None)."""
    from grove.models import Grove, Trunk, Stem, Bud

    models = {
        'grove': Grove,
        'trunk': Trunk,
        'stem': Stem,
        'bud': Bud,
    }

    model = models.get(item_type)
    if not model:
        return None, None

    item = session.query(model).filter(model.id == item_id).first()
    return item, model


def log_activity(session, item_type: str, item_id: int, event_type: str, content: str = None):
    """Helper to log an activity event."""
    import os
    from grove.models import ActivityLog

    session_id = os.environ.get('CLAUDE_SESSION_ID')

    log_entry = ActivityLog(
        item_type=item_type,
        item_id=item_id,
        event_type=event_type,
        content=content,
        session_id=session_id,
    )
    session.add(log_entry)


@click.group()
@click.version_option()
def _main_group():
    """Grove - Botanical task management with hierarchical alignment.

    Your work grows from seeds to blooming buds on stems,
    supported by trunks, all within your groves.

    Commands for managing buds, stems, trunks, and groves.
    """
    pass


def main():
    """Wrapper for the CLI that shows help on missing arguments."""
    try:
        _main_group(standalone_mode=False)
    except click.MissingParameter as e:
        # The exception contains the context - show help for the specific command
        if e.ctx:
            click.echo(e.ctx.get_help())
            raise SystemExit(0)
        else:
            e.show()
            raise SystemExit(e.exit_code)
    except click.ClickException as e:
        e.show()
        raise SystemExit(e.exit_code)
    except Exception:
        raise


# =============================================================================
# BUD MANAGEMENT (Tasks)
# =============================================================================


@_main_group.command()
@click.argument("title")
@click.option("--stem", "-b", type=int, help="Plant on stem (project) ID")
@click.option("--priority", type=click.Choice(["urgent", "high", "medium", "low"]), default="medium", help="Bud priority")
@click.option("--context", "-c", help="Context tag")
def add(title: str, stem: int | None, priority: str, context: str | None):
    """Plant a new seed (add to inbox).

    Seeds are raw captures that haven't been clarified yet.
    Process them with 'gv seeds' to decide what they become.

    Example: gv add "Review PR" --stem=1 --priority=high
    """
    from grove.db import get_session
    from grove.models import Bud

    with get_session() as session:
        bud = Bud(
            title=title,
            stem_id=stem,
            priority=priority,
            context=context,
            status="seed",
        )
        session.add(bud)
        session.commit()
        console.print(f"[green]Planted seed:[/green] {bud.title} (id: {bud.id})")


@_main_group.command()
def seeds():
    """Show unprocessed seeds (inbox items).

    Seeds are raw captures waiting to be clarified.
    Decide: Is this a bud? A new stem? Or mulch?
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


@_main_group.command(name="list")
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


@_main_group.command()
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


@_main_group.command()
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
        old_status = bud.status
        bud.status = "bloomed"
        bud.completed_at = datetime.utcnow()
        log_activity(session, 'bud', bud.id, 'status_changed', f'{old_status} → bloomed')
        session.commit()
        console.print(f"[green]🌸 Bloomed:[/green] {bud.title}")


@_main_group.command()
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
        old_status = bud.status
        bud.status = "mulch"
        log_activity(session, 'bud', bud.id, 'status_changed', f'{old_status} → mulch')
        session.commit()
        console.print(f"[yellow]Mulched:[/yellow] {bud.title}")


@_main_group.command()
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
        old_status = bud.status
        bud.status = "budding"
        bud.started_at = datetime.utcnow()
        log_activity(session, 'bud', bud.id, 'status_changed', f'{old_status} → budding')
        session.commit()
        console.print(f"[green]Started budding:[/green] {bud.title}")


@_main_group.command()
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
        log_activity(session, 'bud', bud.id, 'status_changed', 'seed → dormant')
        session.commit()
        console.print(f"[green]Planted:[/green] {bud.title} (now dormant, ready to grow)")


# =============================================================================
# DEPENDENCIES
# =============================================================================


@_main_group.command()
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


@_main_group.command()
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


@_main_group.command()
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


@_main_group.command()
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


@_main_group.command()
@click.argument("bud_id", type=int)
def why(bud_id: int):
    """Trace a bud up through stem → trunk → grove.

    Shows why a bud exists by displaying its full hierarchy.
    Buds can link directly to grove/trunk or via stem.

    Example: gv why 123
    """
    from grove.db import get_session
    from grove.models import Bud, Stem, Trunk, Grove

    with get_session() as session:
        bud = session.query(Bud).filter(Bud.id == bud_id).first()
        if not bud:
            console.print(f"[red]Bud not found:[/red] {bud_id}")
            return

        console.print()
        console.print(f"[bold cyan]Bud:[/bold cyan] {bud.title}")
        console.print(f"  [dim]id: {bud.id} | status: {bud.status} | priority: {bud.priority}[/dim]")

        # Track what we've shown to avoid duplicates
        shown_stem = False
        shown_trunk = False
        shown_grove = False

        # Show stem if linked
        if bud.stem_id:
            stem = session.query(Stem).filter(Stem.id == bud.stem_id).first()
            if stem:
                shown_stem = True
                console.print()
                console.print(f"  [bold yellow]↑ Stem:[/bold yellow] {stem.title}")
                console.print(f"    [dim]id: {stem.id} | status: {stem.status}[/dim]")
                if stem.done_when:
                    console.print(f"    [dim]blooms when: {stem.done_when}[/dim]")

                # Show trunk via stem
                if stem.trunk_id:
                    trunk = session.query(Trunk).filter(Trunk.id == stem.trunk_id).first()
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

        # Show direct trunk link if not shown via stem
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
        if not bud.stem_id and not bud.trunk_id and not bud.grove_id:
            console.print()
            console.print("[dim]This bud is not planted on any stem, trunk, or grove.[/dim]")

        console.print()


# =============================================================================
# STEM (Project) MANAGEMENT
# =============================================================================


@_main_group.group()
def stem():
    """Manage stems (projects)."""
    pass


@stem.command()
@click.argument("stem_id", type=int)
@click.argument("beads_path")
def link(stem_id: int, beads_path: str):
    """Link a stem to a beads repository path.

    Sets the beads_repo field on a stem, enabling beads integration
    for tracking AI-native issues associated with this stem.

    Example: gv stem link 1 /path/to/.beads
    Example: gv stem link 1 ../shared/.beads
    """
    import os
    from grove.db import get_session
    from grove.models import Stem

    with get_session() as session:
        br = session.query(Stem).filter(Stem.id == stem_id).first()
        if not s:
            console.print(f"[red]Stem not found:[/red] {stem_id}")
            return

        # Resolve relative paths to absolute
        if not os.path.isabs(beads_path):
            beads_path = os.path.abspath(beads_path)

        br.beads_repo = beads_path
        session.commit()
        console.print(f"[green]Linked:[/green] {br.title} → {beads_path}")


@stem.command(name="list")
def list_stems():
    """List all stems with their beads links."""
    from grove.db import get_session
    from grove.models import Stem

    with get_session() as session:
        stems = session.query(Stem).order_by(Stem.title).all()
        if not stems:
            console.print("[dim]No stems[/dim]")
            return

        console.print("[bold]Stems:[/bold]")
        for br in stems:
            status_icon = "●" if br.status == "completed" else "○"
            beads_info = f" → {br.beads_repo}" if br.beads_repo else ""
            console.print(f"  {br.id}: {status_icon} {br.title}[dim]{beads_info}[/dim]")


@stem.command()
@click.argument("stem_id", type=int)
def show(stem_id: int):
    """Show stem details including beads link."""
    from grove.db import get_session
    from grove.models import Stem, Bud

    with get_session() as session:
        br = session.query(Stem).filter(Stem.id == stem_id).first()
        if not br:
            console.print(f"[red]Stem not found:[/red] {stem_id}")
            return

        console.print()
        console.print(f"[bold yellow]Stem:[/bold yellow] {br.title}")
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
        bud_count = session.query(Bud).filter(Bud.stem_id == br.id).count()
        bloomed_count = session.query(Bud).filter(Bud.stem_id == br.id, Bud.status == "bloomed").count()
        console.print(f"  [dim]buds: {bloomed_count}/{bud_count} bloomed[/dim]")
        console.print()


@stem.command(name="new")
@click.argument("title")
@click.option("--trunk", "-t", "trunk_id", type=int, help="Link to trunk ID")
@click.option("--grove", "-g", "grove_id", type=int, help="Link to grove ID")
@click.option("--description", "-d", help="Stem description")
@click.option("--done-when", help="Completion criteria")
def stem_new(title: str, trunk_id: int | None, grove_id: int | None, description: str | None, done_when: str | None):
    """Create a new stem (project).

    Example: gv stem new "Auth System" --trunk=1
    Example: gv stem new "Side Project" --grove=2
    """
    from grove.db import get_session
    from grove.models import Stem, Trunk, Grove

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

        br = Stem(
            title=title,
            trunk_id=trunk_id,
            grove_id=grove_id,
            description=description,
            done_when=done_when,
        )
        session.add(br)
        session.commit()
        console.print(f"[green]Created stem:[/green] {br.id}: {title}")


@stem.command()
@click.argument("stem_id", type=int)
def unlink(stem_id: int):
    """Remove beads link from a stem."""
    from grove.db import get_session
    from grove.models import Stem

    with get_session() as session:
        br = session.query(Stem).filter(Stem.id == stem_id).first()
        if not s:
            console.print(f"[red]Stem not found:[/red] {stem_id}")
            return

        if not br.beads_repo:
            console.print("[yellow]Stem not linked to beads[/yellow]")
            return

        old_path = br.beads_repo
        br.beads_repo = None
        session.commit()
        console.print(f"[green]Unlinked:[/green] {br.title} (was: {old_path})")


# =============================================================================
# BEADS INTEGRATION
# =============================================================================


@_main_group.group()
def beads():
    """Beads integration commands for syncing with AI-native issue tracking."""
    pass


@beads.command()
@click.argument("stem_id", type=int)
@click.argument("bud_ids", nargs=-1, type=int)
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without creating issues")
def push(stem_id: int, bud_ids: tuple, dry_run: bool):
    """Push buds to beads in the linked repository.

    Exports buds from a stem as beads issues. If bud_ids are provided,
    only those buds are pushed. Otherwise, all seed/budding buds in the stem
    are pushed.

    Example: gv beads push 1
    Example: gv beads push 1 10 11 12
    """
    import os
    import subprocess
    from grove.db import get_session
    from grove.models import Stem, Bud

    with get_session() as session:
        br = session.query(Stem).filter(Stem.id == stem_id).first()
        if not s:
            console.print(f"[red]Stem not found:[/red] {stem_id}")
            return

        if not br.beads_repo:
            console.print("[red]Stem not linked to beads.[/red] Use 'gv stem link' first.")
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
                Bud.stem_id == stem_id
            ).all()
            if len(buds) != len(bud_ids):
                found_ids = {b.id for b in buds}
                missing = [bid for bid in bud_ids if bid not in found_ids]
                console.print(f"[yellow]Warning: Buds not found in stem: {missing}[/yellow]")
        else:
            # Get all seed/budding buds in the stem
            buds = session.query(Bud).filter(
                Bud.stem_id == stem_id,
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
@click.argument("stem_id", type=int)
@click.option("--dry-run", is_flag=True, help="Show what would be imported without creating buds")
@click.option("--all", "import_all", is_flag=True, help="Import all beads, not just open ones")
def pull(stem_id: int, dry_run: bool, import_all: bool):
    """Pull beads from linked repository as buds.

    Imports open beads from the stem's linked beads repo as buds.
    Skips beads that have already been imported (matched by beads_id).

    Example: gv beads pull 1
    Example: gv beads pull 1 --all
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Stem, Bud
    from grove.beads import (
        resolve_beads_path,
        read_beads_jsonl,
        filter_open_beads,
        map_bead_status_to_bud_status,
        map_bead_priority_to_importance,
    )

    with get_session() as session:
        br = session.query(Stem).filter(Stem.id == stem_id).first()
        if not s:
            console.print(f"[red]Stem not found:[/red] {stem_id}")
            return

        if not br.beads_repo:
            console.print("[red]Stem not linked to beads.[/red] Use 'gv stem link' first.")
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
                Bud.stem_id == stem_id,
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
                    stem_id=stem_id,
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
@click.argument("stem_id", type=int)
@click.option("--dry-run", is_flag=True, help="Show what would be synced without making changes")
def sync(stem_id: int, dry_run: bool):
    """Bidirectional sync between buds and beads.

    1. Pulls new beads as buds (like 'gv beads pull')
    2. Updates bud statuses from changed beads
    3. Reports buds not in beads (candidates for push)

    Example: gv beads sync 1
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Stem, Bud
    from grove.beads import (
        resolve_beads_path,
        read_beads_jsonl,
        filter_open_beads,
        map_bead_status_to_bud_status,
        map_bead_priority_to_importance,
    )

    with get_session() as session:
        br = session.query(Stem).filter(Stem.id == stem_id).first()
        if not s:
            console.print(f"[red]Stem not found:[/red] {stem_id}")
            return

        if not br.beads_repo:
            console.print("[red]Stem not linked to beads.[/red] Use 'gv stem link' first.")
            return

        try:
            beads_dir = resolve_beads_path(br.beads_repo)
            all_beads = read_beads_jsonl(beads_dir)
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            return

        beads_by_id = {b.id: b for b in all_beads}
        open_beads = filter_open_beads(all_beads)

        console.print(f"[cyan]Syncing stem {stem_id} with:[/cyan] {beads_dir}")
        console.print()

        # Phase 1: Pull new beads
        console.print("[bold]Phase 1: Pull new beads[/bold]")
        existing_buds = session.query(Bud).filter(
            Bud.stem_id == stem_id,
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
                        stem_id=stem_id,
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
            Bud.stem_id == stem_id,
            Bud.beads_id.is_(None),
            Bud.status.in_(["seed", "budding"])
        ).all()

        if unlinked_buds:
            for bud in unlinked_buds:
                console.print(f"  [dim]Not in beads:[/dim] {bud.id}: {bud.title}")
            console.print(f"\n  [dim]Run 'gv beads push {stem_id}' to export these[/dim]")
        else:
            console.print("  [dim]All buds are linked to beads[/dim]")

        console.print()
        console.print(f"[bold]Summary:[/bold] Pulled {pulled}, updated {updated}, {len(unlinked_buds)} unlinked")


@beads.command()
@click.argument("stem_id", type=int)
def status(stem_id: int):
    """Show beads sync status for a stem.

    Displays sync health: linked buds, unlinked buds, stale syncs.

    Example: gv beads status 1
    """
    from datetime import datetime, timedelta
    from grove.db import get_session
    from grove.models import Stem, Bud
    from grove.beads import resolve_beads_path, read_beads_jsonl, filter_open_beads

    with get_session() as session:
        br = session.query(Stem).filter(Stem.id == stem_id).first()
        if not s:
            console.print(f"[red]Stem not found:[/red] {stem_id}")
            return

        console.print(f"[bold]{br.title}[/bold]")
        console.print()

        if not br.beads_repo:
            console.print("[yellow]Not linked to beads[/yellow]")
            console.print(f"[dim]Run 'gv stem link {stem_id} /path/to/.beads' to link[/dim]")
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
        all_buds = session.query(Bud).filter(Bud.stem_id == stem_id).all()
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
            console.print(f"[dim]Run 'gv beads sync {stem_id}' to synchronize[/dim]")


@beads.command()
@click.argument("stem_id", type=int)
@click.option("--recursive", "-r", is_flag=True, help="Include beads on buds within stem")
def hanging(stem_id: int, recursive: bool):
    """Show beads hanging from a stem.

    Lists all beads linked to a stem directly, and optionally beads
    linked to buds within that stem.

    Example: gv beads hanging 1
    Example: gv beads hanging 1 --recursive
    """
    from grove.db import get_session
    from grove.models import Stem, Bud, BeadLink

    with get_session() as session:
        br = session.query(Stem).filter(Stem.id == stem_id).first()
        if not s:
            console.print(f"[red]Stem not found:[/red] {stem_id}")
            return

        console.print(f"[bold]{br.title}[/bold]")
        console.print()

        # Get beads directly on stem
        stem_links = session.query(BeadLink).filter(
            BeadLink.stem_id == stem_id
        ).all()

        if stem_links:
            console.print("[cyan]Beads on stem:[/cyan]")
            for link in stem_links:
                console.print(f"  {link.bead_id} [{link.link_type}]")
        else:
            console.print("[dim]No beads directly on stem[/dim]")

        # Also check legacy buds.beads_id for backward compatibility
        legacy_buds = session.query(Bud).filter(
            Bud.stem_id == stem_id,
            Bud.beads_id.isnot(None)
        ).all()

        if legacy_buds:
            console.print()
            console.print("[cyan]Legacy bead links (via buds.beads_id):[/cyan]")
            for bud in legacy_buds:
                console.print(f"  {bud.beads_id} -> bud {bud.id}: {bud.title[:40]}")

        bud_links = []
        if recursive:
            # Get beads on buds within this stem
            bud_links = session.query(BeadLink).join(
                Bud, BeadLink.bud_id == Bud.id
            ).filter(
                Bud.stem_id == stem_id
            ).all()

            if bud_links:
                console.print()
                console.print("[cyan]Beads on buds in this stem:[/cyan]")
                for link in bud_links:
                    bud = session.query(Bud).filter(Bud.id == link.bud_id).first()
                    bud_title = bud.title[:30] if bud else "unknown"
                    console.print(f"  {link.bead_id} [{link.link_type}] -> bud {link.bud_id}: {bud_title}")
            else:
                console.print()
                console.print("[dim]No beads on buds in this stem[/dim]")

        # Summary
        total = len(stem_links) + len(bud_links) + len(legacy_buds)
        console.print()
        console.print(f"[bold]Total:[/bold] {total} bead(s)")


# =============================================================================
# INDIVIDUAL BEAD OPERATIONS
# =============================================================================


@_main_group.group()
def bead():
    """Individual bead operations (hang, unhang, show)."""
    pass


@bead.command()
@click.argument("bead_id")
@click.option("--bud", "-b", "bud_id", type=int, help="Hang on bud ID")
@click.option("--stem", "-B", "stem_id", type=int, help="Hang on stem ID")
@click.option("--type", "-t", "link_type", default="tracks",
              type=click.Choice(["tracks", "implements", "blocks"]))
def hang(bead_id: str, bud_id: int | None, stem_id: int | None, link_type: str):
    """Hang a bead on a stem or bud.

    Links an external bead (from a beads repo) to a stem or bud.
    The beads_repo is determined from the stem's beads_repo field.

    Example: gv bead hang abc123 --bud 5
    Example: gv bead hang def456 --stem 2 --type implements
    """
    from grove.db import get_session
    from grove.models import Stem, Bud, BeadLink

    # Validate exactly one target
    if bud_id is None and stem_id is None:
        console.print("[red]Error:[/red] Must specify either --bud or --stem")
        return
    if bud_id is not None and stem_id is not None:
        console.print("[red]Error:[/red] Cannot specify both --bud and --stem")
        return

    with get_session() as session:
        beads_repo = None
        target_name = None

        if stem_id is not None:
            # Hanging on a stem
            br = session.query(Stem).filter(Stem.id == stem_id).first()
            if not s:
                console.print(f"[red]Stem not found:[/red] {stem_id}")
                return
            if not br.beads_repo:
                console.print(f"[red]Stem has no beads_repo linked.[/red]")
                console.print(f"[dim]Run 'gv stem link {stem_id} /path/to/.beads' first[/dim]")
                return
            beads_repo = br.beads_repo
            target_name = f"stem {stem_id}: {br.title}"

            # Check for duplicate
            existing = session.query(BeadLink).filter(
                BeadLink.bead_id == bead_id,
                BeadLink.stem_id == stem_id
            ).first()
            if existing:
                console.print(f"[yellow]Bead already hung on this stem[/yellow]")
                return

        else:
            # Hanging on a bud
            bud = session.query(Bud).filter(Bud.id == bud_id).first()
            if not bud:
                console.print(f"[red]Bud not found:[/red] {bud_id}")
                return

            # Get beads_repo from bud's stem
            if bud.stem_id:
                br = session.query(Stem).filter(Stem.id == bud.stem_id).first()
                if br and br.beads_repo:
                    beads_repo = br.beads_repo

            if not beads_repo:
                console.print(f"[red]Cannot determine beads_repo for this bud.[/red]")
                console.print("[dim]The bud's stem must have a beads_repo linked.[/dim]")
                return

            target_name = f"bud {bud_id}: {bud.title}"

            # Check for duplicate
            existing = session.query(BeadLink).filter(
                BeadLink.bead_id == bead_id,
                BeadLink.bud_id == bud_id
            ).first()
            if existing:
                console.print(f"[yellow]Bead already hung on this bud[/yellow]")
                return

        # Create the link
        link = BeadLink(
            bead_id=bead_id,
            bead_repo=beads_repo,
            bud_id=bud_id,
            stem_id=stem_id,
            link_type=link_type,
        )
        session.add(link)
        session.commit()

        console.print(f"[green]Hung bead:[/green] {bead_id} [{link_type}] -> {target_name}")


@bead.command()
@click.argument("bead_id")
@click.option("--bud", "-b", "bud_id", type=int, help="Unhang from specific bud")
@click.option("--stem", "-B", "stem_id", type=int, help="Unhang from specific stem")
def unhang(bead_id: str, bud_id: int | None, stem_id: int | None):
    """Unhang a bead from a stem or bud.

    If neither --bud nor --stem specified, removes all links for this bead.

    Example: gv bead unhang abc123
    Example: gv bead unhang abc123 --bud 5
    """
    from grove.db import get_session
    from grove.models import BeadLink

    with get_session() as session:
        query = session.query(BeadLink).filter(BeadLink.bead_id == bead_id)

        if bud_id is not None:
            query = query.filter(BeadLink.bud_id == bud_id)
        elif stem_id is not None:
            query = query.filter(BeadLink.stem_id == stem_id)

        links = query.all()

        if not links:
            console.print(f"[yellow]No links found for bead:[/yellow] {bead_id}")
            return

        count = len(links)
        for link in links:
            session.delete(link)
        session.commit()

        if bud_id is not None:
            console.print(f"[green]Unhung:[/green] {bead_id} from bud {bud_id}")
        elif stem_id is not None:
            console.print(f"[green]Unhung:[/green] {bead_id} from stem {stem_id}")
        else:
            console.print(f"[green]Unhung:[/green] {bead_id} from {count} location(s)")


@bead.command()
@click.argument("bead_id")
def show(bead_id: str):
    """Show where a bead is hung.

    Displays all stems and buds this bead is linked to.

    Example: gv bead show abc123
    """
    from grove.db import get_session
    from grove.models import Stem, Bud, BeadLink

    with get_session() as session:
        links = session.query(BeadLink).filter(BeadLink.bead_id == bead_id).all()

        if not links:
            console.print(f"[dim]Bead not hung anywhere:[/dim] {bead_id}")
            return

        console.print(f"[bold]Bead:[/bold] {bead_id}")
        console.print()

        for link in links:
            if link.stem_id:
                br = session.query(Stem).filter(Stem.id == link.stem_id).first()
                target = f"stem {link.stem_id}: {br.title}" if br else f"stem {link.stem_id}"
            else:
                bud = session.query(Bud).filter(Bud.id == link.bud_id).first()
                target = f"bud {link.bud_id}: {bud.title}" if bud else f"bud {link.bud_id}"

            console.print(f"  [{link.link_type}] -> {target}")
            console.print(f"    [dim]repo: {link.bead_repo}[/dim]")


# =============================================================================
# OVERVIEW
# =============================================================================


@_main_group.command()
def overview():
    """Show full hierarchy tree with counts and progress.

    Displays all groves, trunks, stems, and bud counts.

    Example: gv overview
    """
    from grove.db import get_session
    from grove.models import Grove, Trunk, Stem, Bud

    with get_session() as session:
        # Get all groves
        groves = session.query(Grove).order_by(Grove.name).all()

        # Get orphan trunks (no grove)
        orphan_trunks = session.query(Trunk).filter(
            Trunk.grove_id.is_(None)
        ).order_by(Trunk.title).all()

        # Get orphan stems (no trunk)
        orphan_stems = session.query(Stem).filter(
            Stem.trunk_id.is_(None)
        ).order_by(Stem.title).all()

        # Get orphan buds (no stem)
        orphan_buds = session.query(Bud).filter(
            Bud.stem_id.is_(None),
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
                stems = session.query(Stem).filter(Stem.trunk_id == trunk.id).all()
                for br in stems:
                    buds = session.query(Bud).filter(Bud.stem_id == br.id).all()
                    grove_bud_count += len(buds)
                    grove_bloomed_count += len([b for b in buds if b.status == "bloomed"])

            progress = f"{grove_bloomed_count}/{grove_bud_count}" if grove_bud_count > 0 else "0/0"
            console.print()
            console.print(f"[bold green]{icon} {grove.name}[/bold green] [{progress}]")

            for trunk in trunks:
                stems = session.query(Stem).filter(Stem.trunk_id == trunk.id).all()

                # Count buds for this trunk
                trunk_bud_count = 0
                trunk_bloomed_count = 0
                for br in stems:
                    buds = session.query(Bud).filter(Bud.stem_id == br.id).all()
                    trunk_bud_count += len(buds)
                    trunk_bloomed_count += len([b for b in buds if b.status == "bloomed"])

                progress = f"{trunk_bloomed_count}/{trunk_bud_count}" if trunk_bud_count > 0 else "0/0"
                status_icon = "○" if trunk.status == "active" else "●"
                console.print(f"  {status_icon} [magenta]{trunk.title}[/magenta] [{progress}]")

                for br in stems:
                    buds = session.query(Bud).filter(Bud.stem_id == br.id).all()
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
                stems = session.query(Stem).filter(Stem.trunk_id == trunk.id).all()
                trunk_bud_count = 0
                trunk_bloomed_count = 0
                for br in stems:
                    buds = session.query(Bud).filter(Bud.stem_id == br.id).all()
                    trunk_bud_count += len(buds)
                    trunk_bloomed_count += len([b for b in buds if b.status == "bloomed"])
                progress = f"{trunk_bloomed_count}/{trunk_bud_count}" if trunk_bud_count > 0 else "0/0"
                console.print(f"  ○ [magenta]{trunk.title}[/magenta] [{progress}]")

        if orphan_stems:
            console.print()
            console.print("[bold dim]Floating Stems[/bold dim]")
            for br in orphan_stems:
                buds = session.query(Bud).filter(Bud.stem_id == br.id).all()
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


@_main_group.command()
def review():
    """Guided weekly review flow.

    Walks through a structured review:
    1. Process seeds (inbox)
    2. Review stale buds
    3. Check blocked work
    4. Review stem progress
    5. Celebrate blooms

    Example: gv review
    """
    from datetime import datetime, timedelta
    from grove.db import get_session
    from grove.models import Bud, Stem, Grove

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

        # Step 4: Stem progress
        console.print("[bold]4. Stem Progress[/bold]")
        stems = session.query(Stem).filter(Stem.status == "active").all()
        if stems:
            for br in stems[:5]:
                buds = session.query(Bud).filter(Bud.stem_id == br.id).all()
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
            if len(stems) > 5:
                console.print(f"   ... and {len(stems) - 5} more stems")
        else:
            console.print("   [dim]No active stems[/dim]")
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


@_main_group.group()
def habit():
    """Habit tracking commands."""
    pass


@habit.command(name="new")
@click.argument("name")
@click.option("--frequency", "-f", default="daily", type=click.Choice(["daily", "weekly", "2x_week", "3x_week"]))
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
            freq_label = {"daily": "d", "weekly": "w", "2x_week": "2x", "3x_week": "3x"}[habit.frequency]
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


@_main_group.group()
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
    """Show trunk details with stems/buds count.

    Example: gv trunk show 1
    """
    from grove.db import get_session
    from grove.models import Trunk, Grove, Stem, Bud

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

        # Count stems under this trunk
        stem_count = session.query(Stem).filter(Stem.trunk_id == trunk.id).count()
        stem_done = session.query(Stem).filter(
            Stem.trunk_id == trunk.id,
            Stem.status == "completed"
        ).count()

        # Count buds under this trunk (direct + via stems)
        direct_bud_count = session.query(Bud).filter(Bud.trunk_id == trunk.id).count()
        direct_bud_bloomed = session.query(Bud).filter(
            Bud.trunk_id == trunk.id,
            Bud.status == "bloomed"
        ).count()

        # Buds via stems
        stem_ids = [b.id for b in session.query(Stem.id).filter(Stem.trunk_id == trunk.id).all()]
        stem_bud_count = session.query(Bud).filter(Bud.stem_id.in_(stem_ids)).count() if stem_ids else 0
        stem_bud_bloomed = session.query(Bud).filter(
            Bud.stem_id.in_(stem_ids),
            Bud.status == "bloomed"
        ).count() if stem_ids else 0

        total_buds = direct_bud_count + stem_bud_count
        total_bloomed = direct_bud_bloomed + stem_bud_bloomed

        console.print()
        console.print(f"  [cyan]Stems:[/cyan] {stem_done}/{stem_count}")
        console.print(f"  [cyan]Buds:[/cyan] {total_bloomed}/{total_buds} ({direct_bud_count} direct, {stem_bud_count} via stems)")

        # List stems if any
        if stem_count > 0:
            console.print()
            console.print("  [bold]Stems:[/bold]")
            stems = session.query(Stem).filter(Stem.trunk_id == trunk.id).order_by(Stem.title).all()
            for br in stems[:10]:
                status_icon = "●" if br.status == "completed" else "○"
                console.print(f"    {status_icon} {br.id}: {br.title}")
            if stem_count > 10:
                console.print(f"    [dim]... and {stem_count - 10} more[/dim]")

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


@_main_group.group()
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

            # Count buds (direct and via trunks/stems)
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
    from grove.models import Grove, Trunk, Stem, Bud

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

        # Buds via trunks and stems
        total_buds = direct_buds
        total_bloomed = direct_bloomed
        for trunk in trunks:
            # Buds directly on trunk
            trunk_buds = session.query(Bud).filter(Bud.trunk_id == trunk.id).count()
            trunk_bloomed = session.query(Bud).filter(Bud.trunk_id == trunk.id, Bud.status == "bloomed").count()
            total_buds += trunk_buds
            total_bloomed += trunk_bloomed

            # Buds via stems
            stems = session.query(Stem).filter(Stem.trunk_id == trunk.id).all()
            for br in stems:
                br_buds = session.query(Bud).filter(Bud.stem_id == br.id).count()
                br_bloomed = session.query(Bud).filter(Bud.stem_id == br.id, Bud.status == "bloomed").count()
                total_buds += br_buds
                total_bloomed += br_bloomed

        # Direct stems under grove
        direct_stems = session.query(Stem).filter(Stem.grove_id == g.id).all()
        for br in direct_stems:
            br_buds = session.query(Bud).filter(Bud.stem_id == br.id).count()
            br_bloomed = session.query(Bud).filter(Bud.stem_id == br.id, Bud.status == "bloomed").count()
            total_buds += br_buds
            total_bloomed += br_bloomed

        console.print("[bold]Statistics[/bold]")
        console.print(f"  Trunks: {len(trunks)}")
        console.print(f"  Direct stems: {len(direct_stems)}")
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
    This does NOT delete trunks, stems, or buds under the grove.

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
# ACTIVITY & REFERENCE COMMANDS
# =============================================================================


def _get_session_id() -> str | None:
    """Get the current Claude session ID from environment."""
    import os
    return os.environ.get('CLAUDE_SESSION_ID')


@_main_group.command(name="log")
@click.argument("ref")
@click.argument("message")
def log_entry(ref: str, message: str):
    """Append a log entry to any item's activity log.

    Uses type prefixes: g:1 (grove), t:5 (trunk), s:12 (stem), b:45 (bud)

    Example: gv log b:45 "Started working on authentication"
    Example: gv log s:12 "Blocked on API design decision"
    """
    from grove.db import get_session
    from grove.models import ActivityLog

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    with get_session() as session:
        item, _ = get_item_by_ref(session, item_type, item_id)
        if not item:
            console.print(f"[red]Not found:[/red] {ref}")
            return

        log = ActivityLog(
            item_type=item_type,
            item_id=item_id,
            event_type='log',
            content=message,
            session_id=_get_session_id()
        )
        session.add(log)
        session.commit()

        title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
        console.print(f"[green]Logged:[/green] {ref} ({title})")
        console.print(f"  [dim]{message}[/dim]")


@_main_group.command()
@click.argument("ref")
@click.argument("value")
@click.option("--note", is_flag=True, help="Mark as Obsidian note")
@click.option("--file", "is_file", is_flag=True, help="Mark as file path")
@click.option("--url", is_flag=True, help="Mark as URL")
@click.option("--label", "-l", help="Optional label for the reference")
def ref(ref: str, value: str, note: bool, is_file: bool, url: bool, label: str | None):
    """Add a structured reference to any item.

    Uses type prefixes: g:1 (grove), t:5 (trunk), s:12 (stem), b:45 (bud)

    Auto-detects type if not specified:
    - [[Note Name]] -> note
    - /path or ~/path -> file
    - http:// or https:// -> url

    Example: gv ref b:45 "[[Project Notes]]"
    Example: gv ref s:12 --file ~/code/project/README.md
    Example: gv ref t:3 --url https://github.com/org/repo --label "Main repo"
    """
    from grove.db import get_session
    from grove.models import Ref as RefModel, ActivityLog

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    # Determine ref_type
    if note:
        ref_type = 'note'
    elif is_file:
        ref_type = 'file'
    elif url:
        ref_type = 'url'
    else:
        # Auto-detect
        if value.startswith('[[') and value.endswith(']]'):
            ref_type = 'note'
        elif value.startswith('/') or value.startswith('~/'):
            ref_type = 'file'
        elif value.startswith('http://') or value.startswith('https://'):
            ref_type = 'url'
        else:
            # Default to note for unrecognized patterns
            ref_type = 'note'
            console.print(f"[dim]Auto-detected as note. Use --file or --url to override.[/dim]")

    with get_session() as session:
        item, _ = get_item_by_ref(session, item_type, item_id)
        if not item:
            console.print(f"[red]Not found:[/red] {ref}")
            return

        new_ref = RefModel(
            item_type=item_type,
            item_id=item_id,
            ref_type=ref_type,
            value=value,
            label=label
        )
        session.add(new_ref)

        # Log the ref addition
        log = ActivityLog(
            item_type=item_type,
            item_id=item_id,
            event_type='ref_added',
            content=f"[{ref_type}] {value}",
            session_id=_get_session_id()
        )
        session.add(log)
        session.commit()

        title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
        label_display = f" ({label})" if label else ""
        console.print(f"[green]Added ref:[/green] {ref} ({title})")
        console.print(f"  [{ref_type}] {value}{label_display}")


@_main_group.command()
@click.argument("ref")
@click.option("--since", help="Filter to activity since (e.g., '2 days ago', '1 week')")
@click.option("--limit", "-n", default=20, help="Max entries to show")
def activity(ref: str, since: str | None, limit: int):
    """Show activity timeline for any item.

    Uses type prefixes: g:1 (grove), t:5 (trunk), s:12 (stem), b:45 (bud)

    Example: gv activity b:45
    Example: gv activity s:12 --since "2 days ago"
    Example: gv activity t:3 -n 50
    """
    from datetime import datetime, timedelta
    from grove.db import get_session
    from grove.models import ActivityLog

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    with get_session() as session:
        item, _ = get_item_by_ref(session, item_type, item_id)
        if not item:
            console.print(f"[red]Not found:[/red] {ref}")
            return

        query = session.query(ActivityLog).filter(
            ActivityLog.item_type == item_type,
            ActivityLog.item_id == item_id
        )

        # Parse --since if provided
        if since:
            import re
            now = datetime.utcnow()
            # Simple parsing for common patterns
            match = re.match(r'(\d+)\s*(day|days|week|weeks|hour|hours|h|d|w)', since.lower())
            if match:
                num = int(match.group(1))
                unit = match.group(2)
                if unit in ('hour', 'hours', 'h'):
                    delta = timedelta(hours=num)
                elif unit in ('day', 'days', 'd'):
                    delta = timedelta(days=num)
                elif unit in ('week', 'weeks', 'w'):
                    delta = timedelta(weeks=num)
                else:
                    delta = timedelta(days=num)
                since_dt = now - delta
                query = query.filter(ActivityLog.created_at >= since_dt)
            else:
                console.print(f"[yellow]Could not parse --since '{since}', showing all[/yellow]")

        activities = query.order_by(ActivityLog.created_at.desc()).limit(limit).all()

        title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
        console.print()
        console.print(f"[bold]Activity for {ref}:[/bold] {title}")
        console.print()

        if not activities:
            console.print("[dim]No activity recorded[/dim]")
            return

        now = datetime.utcnow()

        for a in activities:
            ago = _format_relative_time(a.created_at)
            content = f": {a.content}" if a.content else ""
            session_marker = " [dim]•[/dim]" if a.session_id else ""
            console.print(f"  [{a.event_type}] {ago}{content}{session_marker}")

        console.print()
        total = session.query(ActivityLog).filter(
            ActivityLog.item_type == item_type,
            ActivityLog.item_id == item_id
        ).count()
        if total > limit:
            console.print(f"[dim]Showing {limit} of {total} entries[/dim]")


# =============================================================================
# CONTEXT COMMAND - Show full context for an item
# =============================================================================


def _format_relative_time(dt) -> str:
    """Format a datetime as relative time (e.g., '2h ago', '3d ago')."""
    from datetime import datetime, timezone

    if dt is None:
        return "never"

    # Handle timezone-aware vs naive datetimes
    now = datetime.now(timezone.utc) if dt.tzinfo else datetime.utcnow()
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins}m ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    else:
        days = int(seconds / 86400)
        return f"{days}d ago"


@_main_group.command()
@click.argument("ref")
@click.option("--peek", is_flag=True, help="View without updating last_checked_at")
@click.option("--brief", is_flag=True, help="Show condensed output for scanning")
def context(ref: str, peek: bool, brief: bool):
    """Show full context for an item with temporal awareness.

    Uses type prefixes: g:1 (grove), t:16 (trunk), s:12 (stem), b:45 (bud)

    Shows item details, hierarchy, refs, and recent activity.
    Updates last_checked_at unless --peek is used.

    Example: gv context b:45
    Example: gv context s:12 --brief
    Example: gv context t:16 --peek
    """
    from datetime import datetime, timedelta
    from grove.db import get_session
    from grove.models import Grove, Trunk, Stem, Bud, ActivityLog, Ref

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    with get_session() as session:
        item, model = get_item_by_ref(session, item_type, item_id)

        if not item:
            console.print(f"[red]{item_type.title()} not found:[/red] {item_id}")
            return

        # Get last_checked_at before we update it
        last_checked = item.last_checked_at

        # Calculate activity since last check
        activity_query = session.query(ActivityLog).filter(
            ActivityLog.item_type == item_type,
            ActivityLog.item_id == item_id
        )

        if last_checked:
            new_activity = activity_query.filter(ActivityLog.created_at > last_checked).count()
        else:
            new_activity = activity_query.count()

        total_activity = activity_query.count()

        # Get refs
        refs = session.query(Ref).filter(
            Ref.item_type == item_type,
            Ref.item_id == item_id
        ).all()

        if brief:
            # Brief output for scanning
            title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
            status = getattr(item, 'status', '-')

            last_str = "never" if not last_checked else _format_relative_time(last_checked)
            new_str = f"+{new_activity}" if new_activity else ""

            console.print(f"[bold]{ref}[/bold] {title} [{status}] checked:{last_str} {new_str}")
        else:
            # Full output
            console.print()

            # Header
            title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
            icon = {'grove': '🌳', 'trunk': '🪵', 'stem': '🌿', 'bud': '🌱'}.get(item_type, '')
            console.print(f"[bold]{icon} {item_type.title()}:[/bold] {title}")
            console.print(f"  [dim]id: {item_id}[/dim]", end="")

            if hasattr(item, 'status'):
                console.print(f" [dim]| status: {item.status}[/dim]", end="")
            if hasattr(item, 'priority'):
                console.print(f" [dim]| priority: {item.priority}[/dim]", end="")
            console.print()

            if hasattr(item, 'description') and item.description:
                console.print(f"  [dim]{item.description}[/dim]")

            # Temporal info
            console.print()
            console.print("[bold]Temporal[/bold]")
            if last_checked:
                console.print(f"  Last checked: {_format_relative_time(last_checked)}")
                if new_activity:
                    console.print(f"  [yellow]New activity since last check: {new_activity}[/yellow]")
            else:
                console.print("  [dim]Never checked[/dim]")
            console.print(f"  Total activity entries: {total_activity}")

            # Refs
            if refs:
                console.print()
                console.print("[bold]References[/bold]")
                for r in refs:
                    label = f" ({r.label})" if r.label else ""
                    console.print(f"  [{r.ref_type}] {r.value}{label}")

            # Show hierarchy based on item type
            if item_type == 'bud':
                console.print()
                console.print("[bold]Hierarchy[/bold]")
                if item.stem_id:
                    stem = session.query(Stem).filter(Stem.id == item.stem_id).first()
                    if stem:
                        console.print(f"  ↑ Stem: {stem.title} (s:{stem.id})")
                        if stem.trunk_id:
                            trunk = session.query(Trunk).filter(Trunk.id == stem.trunk_id).first()
                            if trunk:
                                console.print(f"    ↑ Trunk: {trunk.title} (t:{trunk.id})")
                elif item.trunk_id:
                    trunk = session.query(Trunk).filter(Trunk.id == item.trunk_id).first()
                    if trunk:
                        console.print(f"  ↑ Trunk: {trunk.title} (t:{trunk.id})")

            elif item_type == 'stem':
                console.print()
                console.print("[bold]Hierarchy[/bold]")
                if item.trunk_id:
                    trunk = session.query(Trunk).filter(Trunk.id == item.trunk_id).first()
                    if trunk:
                        console.print(f"  ↑ Trunk: {trunk.title} (t:{trunk.id})")
                bud_count = session.query(Bud).filter(Bud.stem_id == item_id).count()
                console.print(f"  ↓ Buds: {bud_count}")

            elif item_type == 'trunk':
                console.print()
                console.print("[bold]Hierarchy[/bold]")
                if item.grove_id:
                    grove = session.query(Grove).filter(Grove.id == item.grove_id).first()
                    if grove:
                        icon = grove.icon or '🌳'
                        console.print(f"  ↑ Grove: {icon} {grove.name} (g:{grove.id})")
                stem_count = session.query(Stem).filter(Stem.trunk_id == item_id).count()
                console.print(f"  ↓ Stems: {stem_count}")

            # Recent activity
            recent = session.query(ActivityLog).filter(
                ActivityLog.item_type == item_type,
                ActivityLog.item_id == item_id
            ).order_by(ActivityLog.created_at.desc()).limit(5).all()

            if recent:
                console.print()
                console.print("[bold]Recent Activity[/bold]")
                for entry in recent:
                    time_str = _format_relative_time(entry.created_at)
                    content_str = f": {entry.content[:50]}..." if entry.content and len(entry.content) > 50 else (f": {entry.content}" if entry.content else "")
                    console.print(f"  [{entry.event_type}] {time_str}{content_str}")

            console.print()

        # Update last_checked_at unless --peek
        if not peek:
            item.last_checked_at = datetime.utcnow()
            log_activity(session, item_type, item_id, 'checked')
            session.commit()


# =============================================================================
# ALIASES for backward compatibility and convenience
# =============================================================================


# Keep 'done' as alias for 'bloom' for muscle memory
@_main_group.command(name="done")
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
        old_status = bud.status
        bud.status = "bloomed"
        bud.completed_at = datetime.utcnow()
        log_activity(session, 'bud', bud.id, 'status_changed', f'{old_status} → bloomed')
        session.commit()
        console.print(f"[green]🌸 Bloomed:[/green] {bud.title}")


# Keep 'inbox' as alias for 'seeds' for muscle memory
@_main_group.command(name="inbox")
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
@_main_group.command(name="now")
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


# =============================================================================
# ROOTS - Source materials underlying your notes
# =============================================================================


@_main_group.group()
def root():
    """Manage roots (source materials underlying your notes).

    Roots are quotes, transcripts, or other source materials that can be
    linked to multiple buds, stems, trunks, or groves.
    """
    pass


@root.command("new")
@click.argument("content")
@click.option("--label", "-l", help="Short label for the root")
@click.option("--type", "source_type", default="quote",
              type=click.Choice(["quote", "transcript", "session", "note"]),
              help="Type of source material")
def root_new(content: str, label: str | None, source_type: str):
    """Create a new root from a quote or source material.

    Example: gv root new "The best way to predict the future is to invent it."
    Example: gv root new "Meeting transcript..." --type transcript --label "Q4 Planning"
    """
    import os
    from grove.db import get_session
    from grove.models import Root

    session_id = os.environ.get('CLAUDE_SESSION_ID')

    with get_session() as session:
        root_obj = Root(
            content=content,
            source_type=source_type,
            label=label,
            session_id=session_id,
        )
        session.add(root_obj)
        session.commit()

        label_display = f" ({label})" if label else ""
        preview = content[:50] + "..." if len(content) > 50 else content
        console.print(f"[green]Created root {root_obj.id}:[/green]{label_display} [{source_type}]")
        console.print(f"  [dim]{preview}[/dim]")


@root.command("attach")
@click.argument("root_id", type=int)
@click.argument("refs", nargs=-1, required=True)
def root_attach(root_id: int, refs: tuple):
    """Attach a root to one or more items.

    Uses type prefixes: g:1 (grove), t:5 (trunk), s:12 (stem), b:45 (bud)

    Example: gv root attach 1 b:4 b:5 b:6 s:7
    """
    from grove.db import get_session
    from grove.models import Root, RootLink

    with get_session() as session:
        root_obj = session.query(Root).filter(Root.id == root_id).first()
        if not root_obj:
            console.print(f"[red]Root not found:[/red] {root_id}")
            return

        attached = 0
        skipped = 0

        for ref in refs:
            try:
                item_type, item_id = parse_item_ref(ref)
            except click.BadParameter as e:
                console.print(f"[yellow]Skipping {ref}:[/yellow] {e.message}")
                skipped += 1
                continue

            # Verify item exists
            item, _ = get_item_by_ref(session, item_type, item_id)
            if not item:
                console.print(f"[yellow]Skipping {ref}:[/yellow] not found")
                skipped += 1
                continue

            # Check if link already exists
            existing = session.query(RootLink).filter(
                RootLink.root_id == root_id,
                RootLink.item_type == item_type,
                RootLink.item_id == item_id
            ).first()

            if existing:
                console.print(f"[dim]Already linked:[/dim] {ref}")
                skipped += 1
                continue

            link = RootLink(
                root_id=root_id,
                item_type=item_type,
                item_id=item_id
            )
            session.add(link)
            title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
            console.print(f"[green]Attached:[/green] {ref} ({title})")
            attached += 1

        session.commit()

        if attached > 0 or skipped > 0:
            console.print(f"\n[bold]Summary:[/bold] {attached} attached, {skipped} skipped")


@root.command("detach")
@click.argument("root_id", type=int)
@click.argument("refs", nargs=-1, required=True)
def root_detach(root_id: int, refs: tuple):
    """Remove links between a root and items.

    Example: gv root detach 1 b:45
    """
    from grove.db import get_session
    from grove.models import Root, RootLink

    with get_session() as session:
        root_obj = session.query(Root).filter(Root.id == root_id).first()
        if not root_obj:
            console.print(f"[red]Root not found:[/red] {root_id}")
            return

        removed = 0
        not_found = 0

        for ref in refs:
            try:
                item_type, item_id = parse_item_ref(ref)
            except click.BadParameter as e:
                console.print(f"[yellow]Skipping {ref}:[/yellow] {e.message}")
                not_found += 1
                continue

            link = session.query(RootLink).filter(
                RootLink.root_id == root_id,
                RootLink.item_type == item_type,
                RootLink.item_id == item_id
            ).first()

            if not link:
                console.print(f"[dim]Not linked:[/dim] {ref}")
                not_found += 1
                continue

            session.delete(link)
            console.print(f"[green]Detached:[/green] {ref}")
            removed += 1

        session.commit()

        if removed > 0 or not_found > 0:
            console.print(f"\n[bold]Summary:[/bold] {removed} detached, {not_found} not found")


@root.command("show")
@click.argument("root_id", type=int)
def root_show(root_id: int):
    """Show a root and all items linked to it.

    Example: gv root show 1
    """
    from grove.db import get_session
    from grove.models import Root, RootLink

    with get_session() as session:
        root_obj = session.query(Root).filter(Root.id == root_id).first()
        if not root_obj:
            console.print(f"[red]Root not found:[/red] {root_id}")
            return

        # Header
        console.print()
        label_display = f" - {root_obj.label}" if root_obj.label else ""
        console.print(f"[bold]Root {root_obj.id}[/bold]{label_display} [{root_obj.source_type}]")
        console.print()

        # Content
        console.print(f"[cyan]Content:[/cyan]")
        console.print(f"  {root_obj.content}")
        console.print()

        # Linked items
        links = session.query(RootLink).filter(RootLink.root_id == root_id).all()
        if links:
            console.print(f"[cyan]Linked items ({len(links)}):[/cyan]")
            for link in links:
                prefix_map = {'grove': 'g', 'trunk': 't', 'stem': 'br', 'bud': 'b'}
                prefix = prefix_map.get(link.item_type, link.item_type)
                ref_str = f"{prefix}:{link.item_id}"

                item, _ = get_item_by_ref(session, link.item_type, link.item_id)
                if item:
                    title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
                    console.print(f"  {ref_str}: {title}")
                else:
                    console.print(f"  {ref_str}: [dim](deleted)[/dim]")
        else:
            console.print("[dim]No linked items[/dim]")

        # Metadata
        console.print()
        console.print(f"[dim]Created: {root_obj.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
        if root_obj.session_id:
            console.print(f"[dim]Session: {root_obj.session_id}[/dim]")


@root.command("list")
@click.option("--type", "source_type", type=click.Choice(["quote", "transcript", "session", "note"]),
              help="Filter by source type")
@click.option("--limit", "-n", default=20, help="Max roots to show")
def root_list(source_type: str | None, limit: int):
    """List all roots.

    Example: gv root list
    Example: gv root list --type quote -n 50
    """
    from grove.db import get_session
    from grove.models import Root, RootLink
    from sqlalchemy import func

    with get_session() as session:
        query = session.query(Root)
        if source_type:
            query = query.filter(Root.source_type == source_type)
        query = query.order_by(Root.created_at.desc()).limit(limit)

        roots = query.all()

        if not roots:
            console.print("[dim]No roots found[/dim]")
            return

        console.print()
        console.print(f"[bold]Roots ({len(roots)}):[/bold]")
        console.print()

        for root_obj in roots:
            # Count links
            link_count = session.query(func.count(RootLink.id)).filter(
                RootLink.root_id == root_obj.id
            ).scalar()

            label_display = f" - {root_obj.label}" if root_obj.label else ""
            preview = root_obj.content[:60] + "..." if len(root_obj.content) > 60 else root_obj.content
            preview = preview.replace('\n', ' ')

            console.print(f"  [bold]{root_obj.id}[/bold]{label_display} [{root_obj.source_type}] ({link_count} links)")
            console.print(f"    [dim]{preview}[/dim]")
            console.print()


@_main_group.command("roots")
@click.argument("ref")
def show_roots(ref: str):
    """Show all roots linked to an item.

    Uses type prefixes: g:1 (grove), t:5 (trunk), s:12 (stem), b:45 (bud)

    Example: gv roots b:45
    Example: gv roots s:12
    """
    from grove.db import get_session
    from grove.models import Root, RootLink

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    with get_session() as session:
        item, _ = get_item_by_ref(session, item_type, item_id)
        if not item:
            console.print(f"[red]Not found:[/red] {ref}")
            return

        title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')

        # Get linked roots
        roots = session.query(Root).join(RootLink).filter(
            RootLink.item_type == item_type,
            RootLink.item_id == item_id
        ).all()

        console.print()
        console.print(f"[bold]Roots for {ref}:[/bold] {title}")
        console.print()

        if not roots:
            console.print("[dim]No roots linked to this item[/dim]")
            return

        for root_obj in roots:
            label_display = f" - {root_obj.label}" if root_obj.label else ""
            preview = root_obj.content[:80] + "..." if len(root_obj.content) > 80 else root_obj.content
            preview = preview.replace('\n', ' ')

            console.print(f"  [bold]{root_obj.id}[/bold]{label_display} [{root_obj.source_type}]")
            console.print(f"    [dim]{preview}[/dim]")
            console.print()


# =============================================================================
# TIDY - Grove maintenance and refactoring
# =============================================================================


@_main_group.group()
def tidy():
    """Grove tidying commands for detecting and refactoring overgrown hierarchies.

    Helps maintain a healthy grove by identifying when trunks have too many
    stems, stems have too many buds, or hierarchies need restructuring.
    """
    pass


def get_tidy_threshold(session, key: str, default: int = 10) -> int:
    """Get a tidy threshold from config, with fallback to default."""
    from grove.models import TidyConfig
    config = session.query(TidyConfig).filter(TidyConfig.key == key).first()
    return config.value if config else default


@tidy.command()
@click.option("--threshold", "-t", type=int, help="Override threshold for overgrown detection")
@click.argument("scope", required=False)
@click.option("--json", "output_json", is_flag=True, help="Machine-readable JSON output")
def scan(threshold: int | None, scope: str | None, output_json: bool):
    """Detect overgrown areas in the grove.

    Scans for trunks with too many stems, stems with too many buds,
    and other hierarchy issues that might benefit from refactoring.

    SCOPE can be a trunk reference (t:5) to limit scanning.

    Examples:
        gv tidy scan                    # Scan everything
        gv tidy scan --threshold 8      # Custom threshold
        gv tidy scan t:5                # Scope to specific trunk
        gv tidy scan --json             # Machine-readable output
    """
    import json
    from grove.db import get_session
    from grove.models import Trunk, Stem, Bud, Fruit

    with get_session() as session:
        # Get thresholds
        stems_threshold = threshold or get_tidy_threshold(session, 'stems_per_trunk', 10)
        buds_threshold = threshold or get_tidy_threshold(session, 'buds_per_stem', 10)
        fruits_threshold = threshold or get_tidy_threshold(session, 'fruits_per_trunk', 10)

        overgrown = {
            'trunks': [],
            'stems': [],
            'fruits': [],
        }

        # Scope filtering
        trunk_filter = None
        if scope:
            try:
                item_type, item_id = parse_item_ref(scope)
                if item_type != 'trunk':
                    console.print(f"[red]Scope must be a trunk (t:id), got {item_type}[/red]")
                    return
                trunk_filter = item_id
            except click.BadParameter as e:
                console.print(f"[red]{e.message}[/red]")
                return

        # Scan trunks for overgrown stems
        trunk_query = session.query(Trunk)
        if trunk_filter:
            trunk_query = trunk_query.filter(Trunk.id == trunk_filter)

        for trunk in trunk_query.all():
            stem_count = session.query(Stem).filter(Stem.trunk_id == trunk.id).count()
            if stem_count > stems_threshold:
                overgrown['trunks'].append({
                    'id': trunk.id,
                    'title': trunk.title,
                    'count': stem_count,
                    'threshold': stems_threshold,
                    'excess': stem_count - stems_threshold,
                })

            # Check fruits per trunk
            fruit_count = session.query(Fruit).filter(Fruit.trunk_id == trunk.id).count()
            if fruit_count > fruits_threshold:
                overgrown['fruits'].append({
                    'trunk_id': trunk.id,
                    'trunk_title': trunk.title,
                    'count': fruit_count,
                    'threshold': fruits_threshold,
                    'excess': fruit_count - fruits_threshold,
                })

        # Scan stems for overgrown buds
        stem_query = session.query(Stem)
        if trunk_filter:
            stem_query = stem_query.filter(Stem.trunk_id == trunk_filter)

        for stem in stem_query.all():
            bud_count = session.query(Bud).filter(Bud.stem_id == stem.id).count()
            if bud_count > buds_threshold:
                overgrown['stems'].append({
                    'id': stem.id,
                    'title': stem.title,
                    'trunk_id': stem.trunk_id,
                    'count': bud_count,
                    'threshold': buds_threshold,
                    'excess': bud_count - buds_threshold,
                })

        # Log the scan activity
        log_activity(session, 'grove', 0, 'tidy_scan',
                    f"Scanned with threshold {threshold or 'default'}, found {len(overgrown['trunks'])} overgrown trunks, {len(overgrown['stems'])} overgrown stems")
        session.commit()

        # Output
        if output_json:
            console.print(json.dumps(overgrown, indent=2))
            return

        total_issues = len(overgrown['trunks']) + len(overgrown['stems']) + len(overgrown['fruits'])

        if total_issues == 0:
            console.print("[green]Grove is tidy![/green] No overgrown areas detected.")
            console.print(f"[dim]Thresholds: {stems_threshold} stems/trunk, {buds_threshold} buds/stem, {fruits_threshold} fruits/trunk[/dim]")
            return

        console.print(f"[yellow]Found {total_issues} overgrown area(s)[/yellow]")
        console.print()

        if overgrown['trunks']:
            console.print("[bold]Overgrown Trunks[/bold] (too many stems):")
            for t in overgrown['trunks']:
                console.print(f"  t:{t['id']} {t['title']}")
                console.print(f"    [yellow]{t['count']} stems[/yellow] (threshold: {t['threshold']}, excess: +{t['excess']})")
            console.print()

        if overgrown['stems']:
            console.print("[bold]Overgrown Stems[/bold] (too many buds):")
            for b in overgrown['stems']:
                console.print(f"  s:{b['id']} {b['title']}")
                console.print(f"    [yellow]{b['count']} buds[/yellow] (threshold: {b['threshold']}, excess: +{b['excess']})")
            console.print()

        if overgrown['fruits']:
            console.print("[bold]Overgrown Fruit Sets[/bold] (too many fruits per trunk):")
            for f in overgrown['fruits']:
                console.print(f"  t:{f['trunk_id']} {f['trunk_title']}")
                console.print(f"    [yellow]{f['count']} fruits[/yellow] (threshold: {f['threshold']}, excess: +{f['excess']})")
            console.print()

        console.print("[dim]Use 'gv tidy suggest <ref>' for refactoring suggestions[/dim]")


@tidy.command()
@click.argument("ref")
def suggest(ref: str):
    """Get refactoring suggestions for an overgrown item.

    Analyzes the item and suggests strategies like:
    - Grouping items into sub-trunks or sub-stems
    - Archiving inactive items
    - Merging similar items

    Examples:
        gv tidy suggest t:3    # Suggestions for trunk with many stems
        gv tidy suggest s:12  # Suggestions for stem with many buds
    """
    from datetime import datetime, timedelta, timezone
    from grove.db import get_session
    from grove.models import Trunk, Stem, Bud

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    with get_session() as session:
        if item_type == 'trunk':
            trunk = session.query(Trunk).filter(Trunk.id == item_id).first()
            if not trunk:
                console.print(f"[red]Trunk not found:[/red] {item_id}")
                return

            stems = session.query(Stem).filter(Stem.trunk_id == trunk.id).all()

            console.print()
            console.print(f"[bold]Suggestions for t:{trunk.id} {trunk.title}[/bold]")
            console.print(f"[dim]{len(stems)} stems[/dim]")
            console.print()

            # Group by labels
            label_groups = {}
            unlabeled = []
            for br in stems:
                if br.labels:
                    for label in br.labels:
                        if label not in label_groups:
                            label_groups[label] = []
                        label_groups[label].append(br)
                else:
                    unlabeled.append(br)

            if label_groups:
                console.print("[cyan]1. Group by labels into sub-trunks:[/cyan]")
                for label, brs in sorted(label_groups.items(), key=lambda x: -len(x[1])):
                    if len(brs) >= 2:
                        console.print(f"   '{label}': {len(brs)} stems")
                        for br in brs[:3]:
                            console.print(f"      - s:{br.id} {br.title}")
                        if len(brs) > 3:
                            console.print(f"      ... and {len(brs) - 3} more")
                console.print()

            # Find inactive stems
            stale_threshold = datetime.now(timezone.utc) - timedelta(days=30)
            inactive = [br for br in stems if br.updated_at and br.updated_at < stale_threshold]
            if inactive:
                console.print("[cyan]2. Archive inactive stems (no updates in 30+ days):[/cyan]")
                for br in inactive[:5]:
                    days = (datetime.now(timezone.utc) - br.updated_at).days
                    console.print(f"   s:{br.id} {br.title} ({days}d inactive)")
                if len(inactive) > 5:
                    console.print(f"   ... and {len(inactive) - 5} more")
                console.print()

            # Find completed stems
            completed = [br for br in stems if br.status == 'completed']
            if completed:
                console.print("[cyan]3. Move completed stems to archive:[/cyan]")
                for br in completed[:5]:
                    console.print(f"   s:{br.id} {br.title}")
                if len(completed) > 5:
                    console.print(f"   ... and {len(completed) - 5} more")
                console.print()

            # Suggest splitting
            if len(stems) > 15:
                console.print("[cyan]4. Consider splitting trunk:[/cyan]")
                console.print(f"   With {len(stems)} stems, consider using 'gv tidy split t:{trunk.id}'")
                console.print("   to interactively divide into 2-3 sub-trunks")
                console.print()

        elif item_type == 'stem':
            stem = session.query(Stem).filter(Stem.id == item_id).first()
            if not stem:
                console.print(f"[red]Stem not found:[/red] {item_id}")
                return

            buds = session.query(Bud).filter(Bud.stem_id == stem.id).all()

            console.print()
            console.print(f"[bold]Suggestions for s:{stem.id} {stem.title}[/bold]")
            console.print(f"[dim]{len(buds)} buds[/dim]")
            console.print()

            # Group by status
            status_groups = {}
            for bud in buds:
                if bud.status not in status_groups:
                    status_groups[bud.status] = []
                status_groups[bud.status].append(bud)

            if status_groups:
                console.print("[cyan]1. Buds by status:[/cyan]")
                for status, bud_list in sorted(status_groups.items(), key=lambda x: -len(x[1])):
                    console.print(f"   {status}: {len(bud_list)} buds")
                console.print()

            # Find bloomed buds to archive
            bloomed = status_groups.get('bloomed', [])
            if bloomed:
                console.print("[cyan]2. Archive bloomed buds:[/cyan]")
                console.print(f"   {len(bloomed)} completed buds could be archived")
                console.print()

            # Find mulched buds
            mulched = status_groups.get('mulch', [])
            if mulched:
                console.print("[cyan]3. Clean up mulched buds:[/cyan]")
                console.print(f"   {len(mulched)} abandoned buds could be removed")
                console.print()

            # Group by labels
            label_groups = {}
            for bud in buds:
                if bud.labels:
                    for label in bud.labels:
                        if label not in label_groups:
                            label_groups[label] = []
                        label_groups[label].append(bud)

            if label_groups:
                console.print("[cyan]4. Group by labels into sub-stems:[/cyan]")
                for label, bud_list in sorted(label_groups.items(), key=lambda x: -len(x[1])):
                    if len(bud_list) >= 3:
                        console.print(f"   '{label}': {len(bud_list)} buds")
                console.print()

            # Suggest splitting
            active_buds = [b for b in buds if b.status in ('seed', 'dormant', 'budding')]
            if len(active_buds) > 15:
                console.print("[cyan]5. Consider splitting stem:[/cyan]")
                console.print(f"   With {len(active_buds)} active buds, consider using 'gv tidy split s:{stem.id}'")
                console.print()

        else:
            console.print(f"[yellow]Suggestions only available for trunks (t:) and stems (s:)[/yellow]")


@tidy.command()
@click.argument("refs", nargs=-1, required=True)
@click.option("--new-trunk", help="Create a new trunk with this title")
@click.option("--new-stem", help="Create a new stem with this title")
@click.option("--parent", help="Parent for new trunk (t:id) or stem (t:id or s:id)")
@click.option("--dry-run", is_flag=True, help="Show what would be moved without making changes")
def graft(refs: tuple, new_trunk: str | None, new_stem: str | None, parent: str | None, dry_run: bool):
    """Move items to a new or existing container.

    Grafts stems onto trunks, or buds onto stems. Can also create
    new containers during the graft operation.

    The last reference is the target (unless --new-trunk or --new-stem is used).

    Examples:
        gv tidy graft s:1 s:2 s:3 t:5              # Move stems to trunk
        gv tidy graft s:1 s:2 --new-trunk "Infra" --parent t:3
        gv tidy graft b:10 b:11 --new-stem "Subtask" --parent s:5
        gv tidy graft s:1 s:2 t:5 --dry-run         # Preview
    """
    from grove.db import get_session
    from grove.models import Trunk, Stem, Bud

    if not refs:
        console.print("[red]No items specified[/red]")
        return

    # When using --new-trunk or --new-stem, all refs are items to move
    # Otherwise, the last ref is the target
    if new_trunk or new_stem:
        items_refs = refs
        target = None
    else:
        if len(refs) < 2:
            console.print("[red]Need at least one item to move and a target[/red]")
            return
        items_refs = refs[:-1]
        target = refs[-1]

    # Parse what we're moving
    items_to_move = []
    item_types = set()
    for ref in items_refs:
        try:
            item_type, item_id = parse_item_ref(ref)
            items_to_move.append((item_type, item_id, ref))
            item_types.add(item_type)
        except click.BadParameter as e:
            console.print(f"[red]Invalid reference '{ref}':[/red] {e.message}")
            return

    if not items_to_move:
        console.print("[red]No valid items to move[/red]")
        return

    # Validate all items are the same type
    if len(item_types) > 1:
        console.print("[red]All items must be the same type (all stems or all buds)[/red]")
        return

    item_type = item_types.pop()

    with get_session() as session:
        # Determine or create target
        target_type = None
        target_id = None
        target_obj = None

        if new_trunk:
            # Creating a new trunk
            if item_type != 'stem':
                console.print("[red]--new-trunk can only be used when grafting stems[/red]")
                return

            parent_id = None
            grove_id = None
            if parent:
                try:
                    p_type, p_id = parse_item_ref(parent)
                    if p_type == 'trunk':
                        parent_id = p_id
                        parent_trunk = session.query(Trunk).filter(Trunk.id == p_id).first()
                        if parent_trunk:
                            grove_id = parent_trunk.grove_id
                    elif p_type == 'grove':
                        grove_id = p_id
                    else:
                        console.print(f"[red]Parent must be a trunk (t:) or grove (g:)[/red]")
                        return
                except click.BadParameter as e:
                    console.print(f"[red]{e.message}[/red]")
                    return

            if dry_run:
                console.print(f"[dim]Would create trunk:[/dim] {new_trunk}")
            else:
                new_trunk_obj = Trunk(
                    title=new_trunk,
                    parent_id=parent_id,
                    grove_id=grove_id,
                    status="active",
                )
                session.add(new_trunk_obj)
                session.flush()
                target_id = new_trunk_obj.id
                target_obj = new_trunk_obj
                console.print(f"[green]Created trunk:[/green] t:{target_id} {new_trunk}")

            target_type = 'trunk'

        elif new_stem:
            # Creating a new stem
            if item_type != 'bud':
                console.print("[red]--new-stem can only be used when grafting buds[/red]")
                return

            trunk_id = None
            parent_stem_id = None
            if parent:
                try:
                    p_type, p_id = parse_item_ref(parent)
                    if p_type == 'trunk':
                        trunk_id = p_id
                    elif p_type == 'stem':
                        parent_stem_id = p_id
                        # Get trunk from parent stem
                        parent_stem = session.query(Stem).filter(Stem.id == p_id).first()
                        if parent_stem:
                            trunk_id = parent_stem.trunk_id
                    else:
                        console.print(f"[red]Parent must be a trunk (t:) or stem (s:)[/red]")
                        return
                except click.BadParameter as e:
                    console.print(f"[red]{e.message}[/red]")
                    return

            if dry_run:
                console.print(f"[dim]Would create stem:[/dim] {new_stem}")
            else:
                new_stem_obj = Stem(
                    title=new_stem,
                    trunk_id=trunk_id,
                    parent_stem_id=parent_stem_id,
                    status="active",
                )
                session.add(new_stem_obj)
                session.flush()
                target_id = new_stem_obj.id
                target_obj = new_stem_obj
                console.print(f"[green]Created stem:[/green] s:{target_id} {new_stem}")

            target_type = 'stem'

        else:
            # Moving to existing target
            try:
                target_type, target_id = parse_item_ref(target)
            except click.BadParameter as e:
                console.print(f"[red]{e.message}[/red]")
                return

            # Validate target type matches items
            if item_type == 'stem' and target_type not in ('trunk', 'stem'):
                console.print("[red]Stems can only be grafted to trunks or parent stems[/red]")
                return
            if item_type == 'bud' and target_type != 'stem':
                console.print("[red]Buds can only be grafted to stems[/red]")
                return

            if target_type == 'trunk':
                target_obj = session.query(Trunk).filter(Trunk.id == target_id).first()
            elif target_type == 'stem':
                target_obj = session.query(Stem).filter(Stem.id == target_id).first()

            if not target_obj:
                console.print(f"[red]Target not found:[/red] {target}")
                return

        # Move items
        moved = 0
        # For dry-run output, determine target display string
        if dry_run and target_id is None:
            if new_trunk:
                target_display = f"new trunk \"{new_trunk}\""
            elif new_stem:
                target_display = f"new stem \"{new_stem}\""
            else:
                target_display = "unknown"
        else:
            target_display = f"t:{target_id}" if target_type == 'trunk' else f"s:{target_id}"

        for _, iid, ref_str in items_to_move:
            if item_type == 'stem':
                item = session.query(Stem).filter(Stem.id == iid).first()
                if not item:
                    console.print(f"[yellow]Stem not found:[/yellow] {ref_str}")
                    continue

                if dry_run:
                    console.print(f"[dim]Would move:[/dim] s:{item.id} {item.title} → {target_display}")
                    moved += 1
                else:
                    old_trunk = item.trunk_id
                    old_parent = item.parent_stem_id
                    if target_type == 'trunk':
                        item.trunk_id = target_id
                        item.parent_stem_id = None
                    else:
                        # Moving to parent stem
                        item.parent_stem_id = target_id
                        # Inherit trunk from target
                        if target_obj:
                            item.trunk_id = target_obj.trunk_id

                    log_activity(session, 'stem', item.id, 'grafted',
                                f'Moved from trunk:{old_trunk}/parent:{old_parent} to {target_type}:{target_id}')
                    console.print(f"[green]Grafted:[/green] s:{item.id} {item.title}")
                    moved += 1

            elif item_type == 'bud':
                item = session.query(Bud).filter(Bud.id == iid).first()
                if not item:
                    console.print(f"[yellow]Bud not found:[/yellow] {ref_str}")
                    continue

                if dry_run:
                    console.print(f"[dim]Would move:[/dim] b:{item.id} {item.title} → {target_display}")
                    moved += 1
                else:
                    old_stem = item.stem_id
                    item.stem_id = target_id
                    log_activity(session, 'bud', item.id, 'grafted',
                                f'Moved from stem:{old_stem} to stem:{target_id}')
                    console.print(f"[green]Grafted:[/green] b:{item.id} {item.title}")
                    moved += 1

        if not dry_run:
            session.commit()

        console.print()
        if dry_run:
            console.print(f"[dim]Dry run complete. Would graft {len(items_to_move)} item(s).[/dim]")
        else:
            console.print(f"[green]Grafted {moved} item(s)[/green]")


@tidy.command()
@click.argument("ref")
@click.option("--auto", is_flag=True, help="Auto-group by labels/keywords")
@click.option("--into", type=int, help="Suggest N-way split")
def split(ref: str, auto: bool, into: int | None):
    """Interactive splitting of overgrown trunks or stems.

    Guides you through splitting a trunk into sub-trunks or a stem
    into sibling/sub-stems.

    Examples:
        gv tidy split t:3           # Interactive split trunk into sub-trunks
        gv tidy split s:12         # Split stem
        gv tidy split t:3 --auto    # Auto-group by labels/keywords
        gv tidy split t:3 --into 3  # Suggest 3-way split
    """
    from grove.db import get_session
    from grove.models import Trunk, Stem, Bud

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    if item_type not in ('trunk', 'stem'):
        console.print("[red]Split only works on trunks (t:) and stems (s:)[/red]")
        return

    with get_session() as session:
        if item_type == 'trunk':
            trunk = session.query(Trunk).filter(Trunk.id == item_id).first()
            if not trunk:
                console.print(f"[red]Trunk not found:[/red] {item_id}")
                return

            stems = session.query(Stem).filter(Stem.trunk_id == trunk.id).all()
            if not stems:
                console.print("[yellow]Trunk has no stems to split[/yellow]")
                return

            console.print()
            console.print(f"[bold]Splitting t:{trunk.id} {trunk.title}[/bold]")
            console.print(f"[dim]{len(stems)} stems[/dim]")
            console.print()

            # Auto-grouping by labels
            if auto:
                label_groups = {}
                unlabeled = []
                for br in stems:
                    if br.labels:
                        primary_label = br.labels[0]  # Use first label as group key
                        if primary_label not in label_groups:
                            label_groups[primary_label] = []
                        label_groups[primary_label].append(br)
                    else:
                        unlabeled.append(br)

                if label_groups:
                    console.print("[cyan]Auto-detected groups by primary label:[/cyan]")
                    console.print()
                    for i, (label, brs) in enumerate(sorted(label_groups.items(), key=lambda x: -len(x[1])), 1):
                        console.print(f"  [bold]{i}. New sub-trunk: '{label}'[/bold]")
                        for br in brs:
                            console.print(f"     s:{br.id} {br.title}")
                        console.print()

                    if unlabeled:
                        console.print(f"  [dim]Unlabeled ({len(unlabeled)} stems would stay):[/dim]")
                        for br in unlabeled[:3]:
                            console.print(f"     s:{br.id} {br.title}")
                        if len(unlabeled) > 3:
                            console.print(f"     ... and {len(unlabeled) - 3} more")
                        console.print()

                    console.print("[dim]Use 'gv tidy graft s:<ids> --new-trunk \"<name>\" --parent t:{item_id}' to execute[/dim]")
                else:
                    console.print("[yellow]No labels found for auto-grouping. Try adding labels to stems first.[/yellow]")
                return

            # Suggest N-way split
            n = into or 2
            if n < 2:
                console.print("[red]Split must be into at least 2 parts[/red]")
                return

            chunk_size = len(stems) // n
            remainder = len(stems) % n

            console.print(f"[cyan]Suggested {n}-way split:[/cyan]")
            console.print()

            sorted_stems = sorted(stems, key=lambda b: b.title)
            start = 0
            for i in range(n):
                size = chunk_size + (1 if i < remainder else 0)
                chunk = sorted_stems[start:start + size]
                start += size

                console.print(f"  [bold]{i + 1}. New sub-trunk ({len(chunk)} stems)[/bold]")
                for br in chunk[:3]:
                    console.print(f"     s:{br.id} {br.title}")
                if len(chunk) > 3:
                    console.print(f"     ... and {len(chunk) - 3} more")
                console.print()

            console.print("[dim]This is a suggestion based on alphabetical order.[/dim]")
            console.print("[dim]Use 'gv tidy graft s:<ids> --new-trunk \"<name>\" --parent t:{item_id}' to execute[/dim]")

        elif item_type == 'stem':
            stem = session.query(Stem).filter(Stem.id == item_id).first()
            if not stem:
                console.print(f"[red]Stem not found:[/red] {item_id}")
                return

            buds = session.query(Bud).filter(Bud.stem_id == stem.id).all()
            if not buds:
                console.print("[yellow]Stem has no buds to split[/yellow]")
                return

            console.print()
            console.print(f"[bold]Splitting s:{stem.id} {stem.title}[/bold]")
            console.print(f"[dim]{len(buds)} buds[/dim]")
            console.print()

            # Auto-grouping by labels
            if auto:
                label_groups = {}
                unlabeled = []
                for bud in buds:
                    if bud.labels:
                        primary_label = bud.labels[0]
                        if primary_label not in label_groups:
                            label_groups[primary_label] = []
                        label_groups[primary_label].append(bud)
                    else:
                        unlabeled.append(bud)

                if label_groups:
                    console.print("[cyan]Auto-detected groups by primary label:[/cyan]")
                    console.print()
                    for i, (label, bud_list) in enumerate(sorted(label_groups.items(), key=lambda x: -len(x[1])), 1):
                        console.print(f"  [bold]{i}. New sub-stem: '{label}'[/bold]")
                        for bud in bud_list[:3]:
                            console.print(f"     b:{bud.id} {bud.title}")
                        if len(bud_list) > 3:
                            console.print(f"     ... and {len(bud_list) - 3} more")
                        console.print()

                    if unlabeled:
                        console.print(f"  [dim]Unlabeled ({len(unlabeled)} buds would stay):[/dim]")
                        for bud in unlabeled[:3]:
                            console.print(f"     b:{bud.id} {bud.title}")
                        if len(unlabeled) > 3:
                            console.print(f"     ... and {len(unlabeled) - 3} more")
                        console.print()

                    console.print(f"[dim]Use 'gv tidy graft b:<ids> --new-stem \"<name>\" --parent s:{item_id}' to execute[/dim]")
                else:
                    console.print("[yellow]No labels found for auto-grouping. Try adding labels to buds first.[/yellow]")
                return

            # Suggest N-way split
            n = into or 2
            if n < 2:
                console.print("[red]Split must be into at least 2 parts[/red]")
                return

            chunk_size = len(buds) // n
            remainder = len(buds) % n

            console.print(f"[cyan]Suggested {n}-way split:[/cyan]")
            console.print()

            sorted_buds = sorted(buds, key=lambda b: b.title)
            start = 0
            for i in range(n):
                size = chunk_size + (1 if i < remainder else 0)
                chunk = sorted_buds[start:start + size]
                start += size

                console.print(f"  [bold]{i + 1}. New sub-stem ({len(chunk)} buds)[/bold]")
                for bud in chunk[:3]:
                    console.print(f"     b:{bud.id} {bud.title}")
                if len(chunk) > 3:
                    console.print(f"     ... and {len(chunk) - 3} more")
                console.print()

            console.print("[dim]This is a suggestion based on alphabetical order.[/dim]")
            console.print(f"[dim]Use 'gv tidy graft b:<ids> --new-stem \"<name>\" --parent s:{item_id}' to execute[/dim]")

        # Log the split analysis
        log_activity(session, item_type, item_id, 'split', f'Split analysis with auto={auto}, into={into}')
        session.commit()


@tidy.command()
@click.option("--set", "set_key", nargs=2, help="Set a threshold (key value)")
def config(set_key: tuple | None):
    """View or configure tidy thresholds.

    Thresholds determine when areas are flagged as overgrown.
    Default: 10 for stems-per-trunk, buds-per-stem, fruits-per-trunk.

    Examples:
        gv tidy config                              # View current thresholds
        gv tidy config --set stems-per-trunk 12 # Set threshold
    """
    from grove.db import get_session
    from grove.models import TidyConfig

    with get_session() as session:
        if set_key:
            key, value_str = set_key
            valid_keys = ['stems-per-trunk', 'buds-per-stem', 'fruits-per-trunk']
            # Normalize key (allow both - and _)
            normalized_key = key.replace('-', '_')

            if normalized_key not in [k.replace('-', '_') for k in valid_keys]:
                console.print(f"[red]Invalid key:[/red] {key}")
                console.print(f"[dim]Valid keys: {', '.join(valid_keys)}[/dim]")
                return

            try:
                value = int(value_str)
                if value < 1:
                    console.print("[red]Threshold must be at least 1[/red]")
                    return
            except ValueError:
                console.print(f"[red]Invalid value:[/red] {value_str} (must be integer)")
                return

            config_obj = session.query(TidyConfig).filter(TidyConfig.key == normalized_key).first()
            if config_obj:
                old_value = config_obj.value
                config_obj.value = value
                console.print(f"[green]Updated:[/green] {normalized_key}: {old_value} → {value}")
            else:
                config_obj = TidyConfig(key=normalized_key, value=value)
                session.add(config_obj)
                console.print(f"[green]Set:[/green] {normalized_key}: {value}")

            session.commit()
            return

        # Show current config
        console.print()
        console.print("[bold]Tidy Thresholds[/bold]")
        console.print()

        defaults = {
            'stems_per_trunk': 10,
            'buds_per_stem': 10,
            'fruits_per_trunk': 10,
        }

        for key, default in defaults.items():
            config_obj = session.query(TidyConfig).filter(TidyConfig.key == key).first()
            value = config_obj.value if config_obj else default
            display_key = key.replace('_', '-')
            is_default = config_obj is None
            default_indicator = " [dim](default)[/dim]" if is_default else ""
            console.print(f"  {display_key}: [cyan]{value}[/cyan]{default_indicator}")

        console.print()
        console.print("[dim]Use --set <key> <value> to change thresholds[/dim]")


# =============================================================================
# POLLEN - AI-generated ideas and external suggestions
# =============================================================================


def parse_duration(duration_str: str):
    """Parse duration strings like '2 days', '1 hour', '30m', '7d'."""
    from datetime import timedelta
    import re

    duration_str = duration_str.strip().lower()
    patterns = [
        (r'^(\d+)\s*d(?:ays?)?$', lambda m: timedelta(days=int(m.group(1)))),
        (r'^(\d+)\s*h(?:ours?)?$', lambda m: timedelta(hours=int(m.group(1)))),
        (r'^(\d+)\s*m(?:in(?:utes?)?)?$', lambda m: timedelta(minutes=int(m.group(1)))),
        (r'^(\d+)\s*w(?:eeks?)?$', lambda m: timedelta(weeks=int(m.group(1)))),
    ]
    for pattern, converter in patterns:
        match = re.match(pattern, duration_str)
        if match:
            return converter(match)
    return None


@_main_group.group()
def pollen():
    """Manage pollen (AI-generated ideas and external suggestions).

    Pollen arrives from AI systems and external sources. It can be
    reviewed and promoted to seeds (buds), or rejected.

    Status lifecycle: pending -> seeded/rejected
    """
    pass


@pollen.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="Include seeded/rejected pollen")
@click.option("--source", "-s", help="Filter by source")
@click.option("--since", help="Filter to pollen since (e.g., '2 days', '1 week')")
@click.option("--limit", "-n", default=20, help="Max entries to show")
def pollen_list(show_all: bool, source: str | None, since: str | None, limit: int):
    """List pending pollen.

    Example: gv pollen list
    Example: gv pollen list --all
    Example: gv pollen list --source claude --since "2 days"
    """
    from datetime import datetime, timedelta
    from grove.db import get_session
    from grove.models import Pollen

    with get_session() as session:
        query = session.query(Pollen)

        if not show_all:
            query = query.filter(Pollen.status == "pending")

        if source:
            query = query.filter(Pollen.source == source)

        if since:
            delta = parse_duration(since)
            if delta:
                since_dt = datetime.utcnow() - delta
                query = query.filter(Pollen.created_at >= since_dt)
            else:
                console.print(f"[yellow]Could not parse --since '{since}', showing all[/yellow]")

        pollen_items = query.order_by(Pollen.created_at.desc()).limit(limit).all()

        if not pollen_items:
            console.print("[dim]No pollen found[/dim]")
            return

        console.print()
        filter_label = "" if show_all else " (pending)"
        console.print(f"[bold]Pollen{filter_label}:[/bold]")
        console.print()

        for p in pollen_items:
            status_icon = {
                "pending": "[yellow]o[/yellow]",
                "seeded": "[green]●[/green]",
                "rejected": "[dim]x[/dim]",
            }.get(p.status, "?")

            preview = p.content[:60] + "..." if len(p.content) > 60 else p.content
            preview = preview.replace('\n', ' ')

            confidence_str = f" ({p.confidence:.0%})" if p.confidence is not None else ""
            console.print(f"  {status_icon} {p.id}: [{p.source}]{confidence_str} {preview}")

        console.print()
        total = session.query(Pollen).filter(Pollen.status == "pending").count()
        console.print(f"[dim]{total} pending pollen total[/dim]")


@pollen.command(name="show")
@click.argument("pollen_id", type=int)
def pollen_show(pollen_id: int):
    """Show full details of a pollen item.

    Example: gv pollen show 5
    """
    from grove.db import get_session
    from grove.models import Pollen, Bud

    with get_session() as session:
        p = session.query(Pollen).filter(Pollen.id == pollen_id).first()
        if not p:
            console.print(f"[red]Pollen not found:[/red] {pollen_id}")
            return

        console.print()
        console.print(f"[bold]Pollen {p.id}[/bold] [{p.status}]")
        console.print()

        console.print(f"[cyan]Source:[/cyan] {p.source}")
        if p.confidence is not None:
            console.print(f"[cyan]Confidence:[/cyan] {p.confidence:.1%}")
        console.print()

        console.print(f"[cyan]Content:[/cyan]")
        console.print(f"  {p.content}")
        console.print()

        if p.source_meta:
            console.print(f"[cyan]Metadata:[/cyan]")
            import json
            console.print(f"  {json.dumps(p.source_meta, indent=2)}")
            console.print()

        if p.status == "seeded" and p.seed_id:
            bud = session.query(Bud).filter(Bud.id == p.seed_id).first()
            if bud:
                console.print(f"[cyan]Became seed:[/cyan] b:{bud.id} {bud.title}")
            else:
                console.print(f"[cyan]Became seed:[/cyan] b:{p.seed_id} (deleted)")
            console.print()

        if p.status == "rejected" and p.reject_reason:
            console.print(f"[cyan]Reject reason:[/cyan] {p.reject_reason}")
            console.print()

        console.print(f"[dim]Created: {p.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
        if p.reviewed_at:
            console.print(f"[dim]Reviewed: {p.reviewed_at.strftime('%Y-%m-%d %H:%M')}[/dim]")


@pollen.command(name="pollinate")
@click.argument("pollen_id", type=int)
@click.option("--stem", "-s", "stem_id", type=int, help="Plant seed on this stem")
def pollen_pollinate(pollen_id: int, stem_id: int | None):
    """Promote pollen to a seed (bud).

    Creates a new bud with status 'seed' from the pollen content.

    Example: gv pollen pollinate 5
    Example: gv pollen pollinate 5 --stem 3
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Pollen, Bud, Stem

    with get_session() as session:
        p = session.query(Pollen).filter(Pollen.id == pollen_id).first()
        if not p:
            console.print(f"[red]Pollen not found:[/red] {pollen_id}")
            return

        if p.status != "pending":
            console.print(f"[yellow]Pollen already {p.status}[/yellow]")
            return

        if stem_id:
            stem = session.query(Stem).filter(Stem.id == stem_id).first()
            if not stem:
                console.print(f"[red]Stem not found:[/red] {stem_id}")
                return

        # Create the seed
        bud = Bud(
            title=p.content[:500],  # Truncate long content for title
            description=p.content if len(p.content) > 500 else None,
            stem_id=stem_id,
            status="seed",
        )
        session.add(bud)
        session.flush()  # Get the bud ID

        # Update pollen
        p.status = "seeded"
        p.seed_id = bud.id
        p.reviewed_at = datetime.utcnow()

        log_activity(session, 'bud', bud.id, 'created', f'From pollen {pollen_id}')
        session.commit()

        stem_info = f" on stem {stem_id}" if stem_id else ""
        console.print(f"[green]Pollinated:[/green] Created seed b:{bud.id}{stem_info}")
        console.print(f"  [dim]{bud.title[:60]}...[/dim]" if len(bud.title) > 60 else f"  [dim]{bud.title}[/dim]")


@pollen.command(name="reject")
@click.argument("pollen_id", type=int)
@click.option("--reason", "-r", help="Reason for rejection")
def pollen_reject(pollen_id: int, reason: str | None):
    """Reject pollen (mark as not useful).

    Example: gv pollen reject 5
    Example: gv pollen reject 5 --reason "Not actionable"
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Pollen

    with get_session() as session:
        p = session.query(Pollen).filter(Pollen.id == pollen_id).first()
        if not p:
            console.print(f"[red]Pollen not found:[/red] {pollen_id}")
            return

        if p.status != "pending":
            console.print(f"[yellow]Pollen already {p.status}[/yellow]")
            return

        p.status = "rejected"
        p.reject_reason = reason
        p.reviewed_at = datetime.utcnow()
        session.commit()

        reason_info = f" ({reason})" if reason else ""
        console.print(f"[yellow]Rejected:[/yellow] Pollen {pollen_id}{reason_info}")


@pollen.command(name="add")
@click.argument("content")
@click.option("--source", "-s", default="manual", help="Source of the pollen")
@click.option("--confidence", "-c", type=float, help="Confidence score (0.0-1.0)")
@click.option("--meta", "-m", help="JSON metadata")
def pollen_add(content: str, source: str, confidence: float | None, meta: str | None):
    """Add pollen manually.

    Example: gv pollen add "Consider adding dark mode"
    Example: gv pollen add "Review API design" --source claude --confidence 0.8
    Example: gv pollen add "From meeting notes" --meta '{"meeting": "2025-01-15"}'
    """
    import json
    from grove.db import get_session
    from grove.models import Pollen

    source_meta = None
    if meta:
        try:
            source_meta = json.loads(meta)
        except json.JSONDecodeError:
            console.print(f"[red]Invalid JSON in --meta:[/red] {meta}")
            return

    if confidence is not None and not (0.0 <= confidence <= 1.0):
        console.print("[red]Confidence must be between 0.0 and 1.0[/red]")
        return

    with get_session() as session:
        p = Pollen(
            content=content,
            source=source,
            source_meta=source_meta,
            confidence=confidence,
        )
        session.add(p)
        session.commit()

        preview = content[:60] + "..." if len(content) > 60 else content
        console.print(f"[green]Added pollen {p.id}:[/green] [{source}] {preview}")


# =============================================================================
# DEW - Ambient data signals
# =============================================================================


@_main_group.group()
def dew():
    """Manage dew (ambient data signals for context enrichment).

    Dew condenses from the environment and nourishes existing items.
    It provides context without creating new work items.

    Status lifecycle: fresh -> absorbed/evaporated
    """
    pass


@dew.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="Include absorbed/evaporated dew")
@click.option("--source", "-s", help="Filter by source")
@click.option("--since", help="Filter to dew since (e.g., '2 days', '1 week')")
@click.option("--limit", "-n", default=20, help="Max entries to show")
def dew_list(show_all: bool, source: str | None, since: str | None, limit: int):
    """List fresh dew.

    Example: gv dew list
    Example: gv dew list --all
    Example: gv dew list --source calendar --since "2 days"
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Dew

    with get_session() as session:
        query = session.query(Dew)

        if not show_all:
            query = query.filter(Dew.status == "fresh")

        if source:
            query = query.filter(Dew.source == source)

        if since:
            delta = parse_duration(since)
            if delta:
                since_dt = datetime.utcnow() - delta
                query = query.filter(Dew.created_at >= since_dt)
            else:
                console.print(f"[yellow]Could not parse --since '{since}', showing all[/yellow]")

        dew_items = query.order_by(Dew.created_at.desc()).limit(limit).all()

        if not dew_items:
            console.print("[dim]No dew found[/dim]")
            return

        console.print()
        filter_label = "" if show_all else " (fresh)"
        console.print(f"[bold]Dew{filter_label}:[/bold]")
        console.print()

        for d in dew_items:
            status_icon = {
                "fresh": "[cyan]o[/cyan]",
                "absorbed": "[green]●[/green]",
                "evaporated": "[dim]~[/dim]",
            }.get(d.status, "?")

            content_preview = ""
            if d.content:
                preview = d.content[:50] + "..." if len(d.content) > 50 else d.content
                content_preview = f" {preview.replace(chr(10), ' ')}"

            attached = ""
            if d.item_type and d.item_id:
                attached = f" -> {d.item_type}:{d.item_id}"

            console.print(f"  {status_icon} {d.id}: [{d.source}]{content_preview}{attached}")

        console.print()
        total = session.query(Dew).filter(Dew.status == "fresh").count()
        console.print(f"[dim]{total} fresh dew total[/dim]")


@dew.command(name="show")
@click.argument("dew_id", type=int)
def dew_show(dew_id: int):
    """Show full details of a dew item.

    Example: gv dew show 5
    """
    import json
    from grove.db import get_session
    from grove.models import Dew

    with get_session() as session:
        d = session.query(Dew).filter(Dew.id == dew_id).first()
        if not d:
            console.print(f"[red]Dew not found:[/red] {dew_id}")
            return

        console.print()
        console.print(f"[bold]Dew {d.id}[/bold] [{d.status}]")
        console.print()

        console.print(f"[cyan]Source:[/cyan] {d.source}")

        if d.content:
            console.print()
            console.print(f"[cyan]Content:[/cyan]")
            console.print(f"  {d.content}")

        if d.payload:
            console.print()
            console.print(f"[cyan]Payload:[/cyan]")
            console.print(f"  {json.dumps(d.payload, indent=2)}")

        if d.source_meta:
            console.print()
            console.print(f"[cyan]Metadata:[/cyan]")
            console.print(f"  {json.dumps(d.source_meta, indent=2)}")

        if d.item_type and d.item_id:
            console.print()
            item, _ = get_item_by_ref(session, _expand_item_type(d.item_type), d.item_id)
            if item:
                title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
                console.print(f"[cyan]Attached to:[/cyan] {d.item_type}:{d.item_id} ({title})")
            else:
                console.print(f"[cyan]Attached to:[/cyan] {d.item_type}:{d.item_id} (deleted)")

        console.print()
        console.print(f"[dim]Created: {d.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
        if d.absorbed_at:
            console.print(f"[dim]Absorbed: {d.absorbed_at.strftime('%Y-%m-%d %H:%M')}[/dim]")
        if d.expires_at:
            console.print(f"[dim]Expires: {d.expires_at.strftime('%Y-%m-%d %H:%M')}[/dim]")


def _expand_item_type(short_type: str) -> str:
    """Expand short item type to full name."""
    type_map = {'g': 'grove', 't': 'trunk', 's': 'stem', 'b': 'bud', 'f': 'fruit'}
    return type_map.get(short_type, short_type)


def _contract_item_type(full_type: str) -> str:
    """Contract full item type to short form."""
    type_map = {'grove': 'g', 'trunk': 't', 'stem': 's', 'bud': 'b', 'fruit': 'f'}
    return type_map.get(full_type, full_type)


@dew.command(name="absorb")
@click.argument("dew_id", type=int)
@click.argument("ref")
def dew_absorb(dew_id: int, ref: str):
    """Attach dew to an item.

    Example: gv dew absorb 5 b:45
    Example: gv dew absorb 3 s:12
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Dew

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    with get_session() as session:
        d = session.query(Dew).filter(Dew.id == dew_id).first()
        if not d:
            console.print(f"[red]Dew not found:[/red] {dew_id}")
            return

        if d.status != "fresh":
            console.print(f"[yellow]Dew already {d.status}[/yellow]")
            return

        item, _ = get_item_by_ref(session, item_type, item_id)
        if not item:
            console.print(f"[red]Not found:[/red] {ref}")
            return

        d.item_type = _contract_item_type(item_type)
        d.item_id = item_id
        d.status = "absorbed"
        d.absorbed_at = datetime.utcnow()

        title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')
        log_activity(session, item_type, item_id, 'dew_absorbed', f'Dew {dew_id} absorbed')
        session.commit()

        console.print(f"[green]Absorbed:[/green] Dew {dew_id} -> {ref} ({title})")


@dew.command(name="on")
@click.argument("ref")
def dew_on(ref: str):
    """Show dew absorbed by an item.

    Example: gv dew on b:45
    Example: gv dew on s:12
    """
    from grove.db import get_session
    from grove.models import Dew

    try:
        item_type, item_id = parse_item_ref(ref)
    except click.BadParameter as e:
        console.print(f"[red]{e.message}[/red]")
        return

    short_type = _contract_item_type(item_type)

    with get_session() as session:
        item, _ = get_item_by_ref(session, item_type, item_id)
        if not item:
            console.print(f"[red]Not found:[/red] {ref}")
            return

        title = getattr(item, 'title', None) or getattr(item, 'name', 'Unknown')

        dew_items = session.query(Dew).filter(
            Dew.item_type == short_type,
            Dew.item_id == item_id
        ).order_by(Dew.created_at.desc()).all()

        console.print()
        console.print(f"[bold]Dew on {ref}:[/bold] {title}")
        console.print()

        if not dew_items:
            console.print("[dim]No dew absorbed by this item[/dim]")
            return

        for d in dew_items:
            content_preview = ""
            if d.content:
                preview = d.content[:50] + "..." if len(d.content) > 50 else d.content
                content_preview = f" {preview.replace(chr(10), ' ')}"

            console.print(f"  {d.id}: [{d.source}]{content_preview}")
            console.print(f"    [dim]absorbed {_format_relative_time(d.absorbed_at)}[/dim]")


@dew.command(name="evaporate")
@click.argument("dew_id", type=int, required=False)
@click.option("--older", help="Evaporate dew older than (e.g., '7 days', '2 weeks')")
@click.option("--source", "-s", help="Filter by source when using --older")
def dew_evaporate(dew_id: int | None, older: str | None, source: str | None):
    """Dismiss dew (mark as evaporated).

    Can evaporate a single dew by ID, or bulk evaporate old dew.

    Example: gv dew evaporate 5
    Example: gv dew evaporate --older "7 days"
    Example: gv dew evaporate --older "2 weeks" --source webhook
    """
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Dew

    if dew_id is None and older is None:
        console.print("[red]Must specify either a dew ID or --older[/red]")
        return

    with get_session() as session:
        if dew_id is not None:
            # Single evaporation
            d = session.query(Dew).filter(Dew.id == dew_id).first()
            if not d:
                console.print(f"[red]Dew not found:[/red] {dew_id}")
                return

            if d.status != "fresh":
                console.print(f"[yellow]Dew already {d.status}[/yellow]")
                return

            d.status = "evaporated"
            session.commit()
            console.print(f"[dim]Evaporated:[/dim] Dew {dew_id}")

        else:
            # Bulk evaporation
            delta = parse_duration(older)
            if not delta:
                console.print(f"[red]Could not parse duration:[/red] {older}")
                return

            threshold = datetime.utcnow() - delta
            query = session.query(Dew).filter(
                Dew.status == "fresh",
                Dew.created_at < threshold
            )

            if source:
                query = query.filter(Dew.source == source)

            count = query.count()
            if count == 0:
                source_info = f" from {source}" if source else ""
                console.print(f"[dim]No fresh dew older than {older}{source_info}[/dim]")
                return

            query.update({"status": "evaporated"})
            session.commit()

            source_info = f" from {source}" if source else ""
            console.print(f"[dim]Evaporated:[/dim] {count} dew item(s) older than {older}{source_info}")


@dew.command(name="add")
@click.option("--content", "-c", help="Text content")
@click.option("--payload", "-p", help="JSON payload")
@click.option("--source", "-s", default="manual", help="Source of the dew")
@click.option("--expires", "-e", help="Expiration duration (e.g., '7 days', '2 weeks')")
@click.option("--meta", "-m", help="JSON metadata")
def dew_add(content: str | None, payload: str | None, source: str, expires: str | None, meta: str | None):
    """Add dew manually.

    Must provide either --content or --payload (or both).

    Example: gv dew add --content "Meeting at 3pm"
    Example: gv dew add --payload '{"event": "deploy", "version": "1.2.3"}' --source webhook
    Example: gv dew add --content "Review needed" --expires "7 days"
    """
    import json
    from datetime import datetime
    from grove.db import get_session
    from grove.models import Dew

    if content is None and payload is None:
        console.print("[red]Must provide either --content or --payload[/red]")
        return

    payload_dict = None
    if payload:
        try:
            payload_dict = json.loads(payload)
        except json.JSONDecodeError:
            console.print(f"[red]Invalid JSON in --payload:[/red] {payload}")
            return

    source_meta = None
    if meta:
        try:
            source_meta = json.loads(meta)
        except json.JSONDecodeError:
            console.print(f"[red]Invalid JSON in --meta:[/red] {meta}")
            return

    expires_at = None
    if expires:
        delta = parse_duration(expires)
        if delta:
            expires_at = datetime.utcnow() + delta
        else:
            console.print(f"[red]Could not parse expiration:[/red] {expires}")
            return

    with get_session() as session:
        d = Dew(
            content=content,
            payload=payload_dict,
            source=source,
            source_meta=source_meta,
            expires_at=expires_at,
        )
        session.add(d)
        session.commit()

        preview = ""
        if content:
            preview = content[:50] + "..." if len(content) > 50 else content
        elif payload_dict:
            preview = str(payload_dict)[:50] + "..."

        expires_info = f" (expires in {expires})" if expires else ""
        console.print(f"[green]Added dew {d.id}:[/green] [{source}] {preview}{expires_info}")


@dew.command(name="l2")
@click.option("--limit", "-n", default=20, help="Number of entries to show")
@click.option("--since", help="Show entries since (e.g., '2 days', '1 week')")
@click.option("--search", "-s", help="Search L2 content")
def dew_l2(limit: int, since: str | None, search: str | None):
    """Show L2 journal entries as potential dew sources.

    L2 entries live in apple_notes.l2_entries (synced by gardener).
    Use this to browse recent journal entries and decide what to absorb as dew.

    Examples:
        gv dew l2                      # Recent 20 entries
        gv dew l2 -n 50                # Recent 50 entries
        gv dew l2 --since "3 days"     # Last 3 days
        gv dew l2 --search "auth"      # Search for "auth"
    """
    from grove.db import get_session
    from sqlalchemy import text, desc
    from datetime import datetime

    with get_session() as session:
        # Build query
        query = "SELECT entry_timestamp, content FROM apple_notes.l2_entries"
        conditions = []
        params = {}

        if since:
            delta = parse_duration(since)
            if delta:
                since_dt = datetime.utcnow() - delta
                conditions.append("entry_timestamp >= :since_dt")
                params["since_dt"] = since_dt

        if search:
            conditions.append("content ILIKE :search")
            params["search"] = f"%{search}%"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY entry_timestamp DESC LIMIT :limit"
        params["limit"] = limit

        result = session.execute(text(query), params)
        entries = result.fetchall()

    if not entries:
        console.print("[dim]No L2 entries found[/dim]")
        console.print()
        console.print("[dim]Tip: Sync L2 with gardener first:[/dim]")
        console.print("  cd ~/code/gardener && gardener-sync-l2")
        return

    console.print()
    console.print(f"[bold]L2 Journal Entries[/bold] ({len(entries)} entries)")
    console.print()

    for entry in entries:
        ts, content = entry
        ts_str = ts.strftime("%b %d, %Y at %I:%M %p") if ts else "No timestamp"

        # Preview content (first 100 chars)
        preview = content[:100] + "..." if len(content) > 100 else content
        preview = preview.replace("\n", " ")

        console.print(f"  [cyan]{ts_str}[/cyan]")
        console.print(f"  {preview}")
        console.print()

    console.print("[dim]To create dew from an entry, use:[/dim]")
    console.print('  gv dew add --content "<entry text>" --source l2:journal')


if __name__ == "__main__":
    main()
