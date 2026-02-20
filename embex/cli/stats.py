"""
embex stats — project-wide statistics and insights.
"""

from __future__ import annotations

import os
import typer

from embex.config import find_project_root, load_config, chroma_path, history_db_path, embex_dir
from embex.core.vector_store import VectorStore
from embex.core.history_store import HistoryStore
from embex.utils.display import console, error

from rich.table import Table
from rich.panel import Panel
from rich import box


def _dir_size(path) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def stats_command() -> None:
    """Show project-wide statistics and insights."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    config = load_config(project_root)

    # Vector store stats
    vector_store = VectorStore(chroma_path(project_root))
    collections = vector_store._client.list_collections()
    total_chunks = 0
    total_collections = len(collections)
    for col in collections:
        total_chunks += col.count()

    # History store stats
    history_store = HistoryStore(history_db_path(project_root))
    cur = history_store._conn.execute(
        "SELECT COUNT(*) as files, COALESCE(SUM(current_version), 0) as versions FROM file_registry"
    )
    row = cur.fetchone()
    total_files = row["files"]
    total_versions = row["versions"]

    # Most changed files
    cur = history_store._conn.execute(
        "SELECT file_path, current_version, language FROM file_registry ORDER BY current_version DESC LIMIT 5"
    )
    top_changed = [dict(r) for r in cur.fetchall()]
    history_store.close()

    # Disk usage
    embex_directory = embex_dir(project_root)
    chroma_size = _dir_size(chroma_path(project_root))
    history_size = os.path.getsize(history_db_path(project_root)) if history_db_path(project_root).exists() else 0
    total_size = _dir_size(embex_directory)

    # Overview panel
    overview = (
        f"[bold cyan]Project:[/bold cyan] {project_root}\n"
        f"[bold cyan]Provider:[/bold cyan] {config.embedding.provider} ({config.embedding.model})\n"
        f"[bold cyan]Chunking:[/bold cyan] {config.chunking.strategy}\n"
    )
    console.print(Panel(overview, title="[bold]Embex Stats[/bold]", box=box.ROUNDED))

    # Numbers table
    numbers = Table(title="Overview", box=box.SIMPLE_HEAVY, title_style="bold yellow")
    numbers.add_column("Metric", style="cyan", min_width=25)
    numbers.add_column("Value", style="bold white", justify="right")
    numbers.add_row("Tracked files", str(total_files))
    numbers.add_row("Total versions (snapshots)", str(total_versions))
    numbers.add_row("Vector collections", str(total_collections))
    numbers.add_row("Total chunks embedded", str(total_chunks))
    numbers.add_row("ChromaDB size", _human_size(chroma_size))
    numbers.add_row("History DB size", _human_size(history_size))
    numbers.add_row("Total .embex/ size", _human_size(total_size))
    console.print(numbers)

    # Most changed files
    if top_changed:
        console.print()
        changed_table = Table(title="Most Changed Files", box=box.ROUNDED, title_style="bold magenta")
        changed_table.add_column("File", style="cyan", min_width=30)
        changed_table.add_column("Language", style="green", width=10)
        changed_table.add_column("Versions", style="yellow", justify="right", width=10)
        for f in top_changed:
            changed_table.add_row(f["file_path"], f.get("language", "?"), str(f["current_version"]))
        console.print(changed_table)

    console.print()
