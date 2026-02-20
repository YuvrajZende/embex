"""
embex memory — agent memory layer: store, recall, and manage semantic memories.

AI agents and developers can persist arbitrary notes, decisions, and facts
that are semantically searchable later.

Subcommands:
    embex memory add "We use JWT for all API auth"
    embex memory recall "authentication approach"
    embex memory list
    embex memory forget <id>
    embex memory clear
"""

from __future__ import annotations

from typing import Optional, Any

import typer

from embex.config import find_project_root, load_config, chroma_path, memory_db_path
from embex.core.embedder import Embedder
from embex.core.memory_store import MemoryStore
from embex.utils.display import console, success, error, info, warning

from rich.table import Table
from rich.markdown import Markdown
from rich import box
from datetime import datetime, timezone

memory_app = typer.Typer(
    name="memory",
    help="Agent memory — store and recall semantic memories about your project.",
    no_args_is_help=True,
)


def _get_store(project_root) -> tuple[MemoryStore, Any, Embedder]:
    from embex.config import load_config
    config = load_config(project_root)
    try:
        embedder = Embedder(config)
    except EnvironmentError as exc:
        error(str(exc))
        raise typer.Exit(1)
    store = MemoryStore(
        db_path=memory_db_path(project_root),
        chroma_dir=chroma_path(project_root),
    )
    return store, config, embedder


@memory_app.command("add")
def memory_add(
    content: str = typer.Argument(..., help="The fact, note, or decision to remember."),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags, e.g. 'auth,security'."),
    agent: str = typer.Option("", "--agent", help="Agent identifier (e.g. 'cursor', 'claude')."),
) -> None:
    """Store a new memory."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    store, config, embedder = _get_store(project_root)
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    try:
        memory_id = store.remember(content, embedder=embedder, tags=tag_list, agent=agent)
        success(f"Memory stored [dim]{memory_id[:8]}...[/dim]")
    finally:
        store.close()


@memory_app.command("recall")
def memory_recall(
    query: str = typer.Argument(..., help="Natural language query to search memories."),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of memories to return."),
    agent: Optional[str] = typer.Option(None, "--agent", help="Filter by agent identifier."),
    min_score: float = typer.Option(0.20, "--min-score", help="Minimum similarity score (0-1)."),
) -> None:
    """Recall the most relevant memories for a query."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    store, config, embedder = _get_store(project_root)

    try:
        results = store.recall(query, embedder=embedder, top_k=top_k, agent=agent, min_score=min_score)
    finally:
        store.close()

    if not results:
        info("No relevant memories found.")
        return

    console.print()
    for i, r in enumerate(results, 1):
        ts = datetime.fromtimestamp(r["created_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        tags_str = f"  [dim]tags: {', '.join(r['tags'])}[/dim]" if r["tags"] else ""
        agent_str = f"  [dim]agent: {r['agent']}[/dim]" if r["agent"] else ""
        console.print(
            f"[bold cyan]{i}.[/bold cyan] [green]score={r['score']:.3f}[/green]  "
            f"[dim]{ts}[/dim]{tags_str}{agent_str}\n"
            f"   {r['content']}\n"
            f"   [dim]id: {r['id'][:8]}...[/dim]\n"
        )


@memory_app.command("list")
def memory_list(
    agent: Optional[str] = typer.Option(None, "--agent", help="Filter by agent identifier."),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number to show."),
) -> None:
    """List stored memories in reverse chronological order."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    store, config, embedder = _get_store(project_root)

    try:
        memories = store.list_memories(agent=agent, limit=limit)
        total = store.count()
    finally:
        store.close()

    if not memories:
        info("No memories stored yet.  Use 'embex memory add' to store one.")
        return

    table = Table(
        title=f"Agent Memories ({total} total)",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("ID", style="dim", width=10)
    table.add_column("Content", ratio=3)
    table.add_column("Tags", ratio=1)
    table.add_column("Agent", ratio=1)
    table.add_column("Stored", style="dim", width=16)

    for m in memories:
        ts = datetime.fromtimestamp(m["created_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        table.add_row(
            m["id"][:8] + "…",
            m["content"][:120] + ("…" if len(m["content"]) > 120 else ""),
            ", ".join(m["tags"]) if m["tags"] else "—",
            m["agent"] or "—",
            ts,
        )

    console.print(table)


@memory_app.command("forget")
def memory_forget(
    memory_id: str = typer.Argument(..., help="Memory ID (or prefix) to delete."),
) -> None:
    """Delete a specific memory by ID."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    store, config, embedder = _get_store(project_root)

    try:
        # Allow prefix matching from list output
        all_mems = store.list_memories(limit=1000)
        matched = [m for m in all_mems if m["id"].startswith(memory_id)]
        if not matched:
            error(f"No memory found with id starting with '{memory_id}'.")
            raise typer.Exit(1)
        full_id = matched[0]["id"]
        deleted = store.forget(full_id)
    finally:
        store.close()

    if deleted:
        success(f"Memory deleted: [dim]{full_id[:8]}...[/dim]")
    else:
        error(f"Memory '{memory_id}' not found.")


@memory_app.command("clear")
def memory_clear(
    agent: Optional[str] = typer.Option(None, "--agent", help="Only clear memories for this agent."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Delete all memories (or all for a specific agent)."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    scope = f"for agent '{agent}'" if agent else "ALL memories"
    if not yes:
        typer.confirm(f"Delete {scope}?", abort=True)

    store, config, embedder = _get_store(project_root)

    try:
        count = store.forget_all(agent=agent or "")
    finally:
        store.close()

    success(f"Deleted {count} memor{'y' if count == 1 else 'ies'}.")
