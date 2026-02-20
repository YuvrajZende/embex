"""
embex status — inspect the embedded database contents.
"""

from __future__ import annotations

import typer

from embex.config import find_project_root, load_config, chroma_path, history_db_path
from embex.core.vector_store import VectorStore
from embex.core.history_store import HistoryStore
from embex.utils.display import console, info, error

from rich.table import Table
from rich import box


def status_command() -> None:
    """Show the current state of the Embex database."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    config = load_config(project_root)

    console.print(f"\n[bold magenta]Embex Project:[/bold magenta] {project_root}")
    console.print(f"[dim]Provider:[/dim] {config.embedding.provider}  |  [dim]Model:[/dim] {config.embedding.model}")
    console.print()

    # --- Vector Store Info ---
    vector_store = VectorStore(chroma_path(project_root))
    collections = vector_store._client.list_collections()

    total_chunks = 0
    col_table = Table(
        title="Vector Store (ChromaDB)",
        box=box.ROUNDED,
        title_style="bold cyan",
    )
    col_table.add_column("Collection", style="cyan", min_width=20)
    col_table.add_column("Folder", style="white")
    col_table.add_column("Chunks", style="yellow", justify="right")

    for col in collections:
        count = col.count()
        total_chunks += count
        folder = col.metadata.get("folder", "?") if col.metadata else "?"
        col_table.add_row(col.name, folder, str(count))

    col_table.add_section()
    col_table.add_row("[bold]Total[/bold]", "", f"[bold]{total_chunks}[/bold]")
    console.print(col_table)
    console.print()

    # --- History Store Info ---
    history_store = HistoryStore(history_db_path(project_root))

    # Get per-file details: current version pointer + total snapshots ever stored
    cur = history_store._conn.execute(
        """
        SELECT
            r.file_path,
            r.current_version,
            r.language,
            COUNT(s.version)              AS total_snapshots,
            MIN(s.version)                AS min_version,
            MAX(s.version)                AS max_version
        FROM file_registry r
        LEFT JOIN snapshots s ON s.file_path = r.file_path
        GROUP BY r.file_path
        ORDER BY r.file_path
        """
    )
    files = [dict(r) for r in cur.fetchall()]

    # Summary counts
    cur2 = history_store._conn.execute(
        "SELECT COUNT(*) AS files, COUNT(*) AS dummy FROM file_registry"
    )
    tracked_files = cur2.fetchone()["files"] or 0
    total_snapshots_all = sum(f["total_snapshots"] for f in files)

    history_store.close()

    file_table = Table(
        title="History Store (SQLite)",
        box=box.ROUNDED,
        title_style="bold cyan",
    )
    file_table.add_column("File",            style="cyan",   min_width=30)
    file_table.add_column("Language",        style="green",  width=12)
    file_table.add_column("Current Version", style="bold yellow", justify="right", width=15)
    file_table.add_column("All Versions",    style="dim white",   justify="right", width=12)

    for f in files:
        total = f["total_snapshots"]
        mn    = f["min_version"]
        mx    = f["max_version"]
        cur_v = f["current_version"]

        # e.g.  "v4"   and  "7  (v1–v7)"
        cur_label   = f"v{cur_v}"
        range_label = f"{total}  (v{mn}–v{mx})" if total > 0 else "—"

        file_table.add_row(
            f["file_path"],
            f.get("language") or "?",
            cur_label,
            range_label,
        )

    file_table.add_section()
    file_table.add_row(
        f"[bold]{tracked_files} file(s)[/bold]",
        "",
        "",
        f"[bold]{total_snapshots_all} snapshot(s)[/bold]",
    )
    console.print(file_table)
    console.print()
