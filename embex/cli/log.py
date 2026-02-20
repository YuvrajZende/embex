"""
embex log — show version history for a tracked file, or recent changes across all files.
"""

from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone

import typer

from embex.config import find_project_root, history_db_path
from embex.core.history_store import HistoryStore
from embex.utils.display import console, print_history_table, error, info

from rich.table import Table
from rich import box


def log_command(
    file_path: Optional[str] = typer.Argument(None, help="Relative path to the file. Omit for all files."),
    all_files: bool = typer.Option(False, "--all", "-a", help="Show recent changes across ALL files."),
    limit: int = typer.Option(20, "--limit", "-n", help="Max entries to show (with --all)."),
) -> None:
    """Show version history for a file, or recent changes across all files."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    history_store = HistoryStore(history_db_path(project_root))

    if all_files or file_path is None:
        # Show recent changes across all files
        cur = history_store._conn.execute(
            """
            SELECT s.file_path, s.version, s.timestamp, s.checksum, s.message
            FROM snapshots s
            ORDER BY s.timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )
        entries = [dict(r) for r in cur.fetchall()]
        history_store.close()

        if not entries:
            info("No history entries found.")
            raise typer.Exit(0)

        table = Table(
            title="Recent Changes (All Files)",
            box=box.ROUNDED,
            title_style="bold cyan",
        )
        table.add_column("File", style="cyan", min_width=25)
        table.add_column("Version", style="yellow", width=8, justify="right")
        table.add_column("Timestamp", style="white", width=20)
        table.add_column("Checksum", style="dim", width=12)

        for e in entries:
            ts = datetime.fromtimestamp(e["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            table.add_row(
                e["file_path"],
                str(e["version"]),
                ts,
                e["checksum"][:10],
            )

        console.print(table)
    else:
        # Single file history
        norm_path = file_path.replace("\\", "/")
        entries = history_store.get_file_history(norm_path)
        history_store.close()

        if not entries:
            info(f"No history found for '{norm_path}'.")
            raise typer.Exit(0)

        print_history_table(entries)
