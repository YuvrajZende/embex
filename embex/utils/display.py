"""
Rich-based terminal output helpers for Embex CLI.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()
error_console = Console(stderr=True)


def success(message: str) -> None:
    """Print a green success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def error(message: str) -> None:
    """Print a red error message to stderr."""
    error_console.print(f"[bold red]✗[/bold red] {message}")


def info(message: str) -> None:
    """Print a blue info message."""
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


def warning(message: str) -> None:
    """Print a yellow warning message."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_results_table(results: list[dict]) -> None:
    """Print query results in a styled Rich table.

    Each dict in *results* should have keys:
    ``file_path``, ``chunk_index``, ``score``, ``preview``
    """
    if not results:
        info("No results found.")
        return

    table = Table(
        title="Search Results",
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold magenta",
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("File", style="cyan", min_width=20)
    table.add_column("Chunk", style="yellow", width=6, justify="center")
    table.add_column("Score", style="green", width=8, justify="right")
    table.add_column("Preview", style="white", max_width=60)

    for i, r in enumerate(results, 1):
        score_str = f"{r['score']:.4f}" if isinstance(r["score"], float) else str(r["score"])
        preview = r.get("preview", "")
        # Truncate long previews
        if len(preview) > 120:
            preview = preview[:117] + "..."
        table.add_row(
            str(i),
            r["file_path"],
            str(r["chunk_index"]),
            score_str,
            preview.replace("\n", " "),
        )

    console.print(table)


def print_diff(diff_lines: list[str], file_path: str, v1: int, v2: int) -> None:
    """Print a coloured unified diff."""
    if not diff_lines:
        info(f"No differences between v{v1} and v{v2} of {file_path}")
        return

    output_parts: list[str] = []
    for line in diff_lines:
        if line.startswith("+") and not line.startswith("+++"):
            output_parts.append(f"[green]{line}[/green]")
        elif line.startswith("-") and not line.startswith("---"):
            output_parts.append(f"[red]{line}[/red]")
        elif line.startswith("@@"):
            output_parts.append(f"[cyan]{line}[/cyan]")
        else:
            output_parts.append(line)

    panel = Panel(
        "\n".join(output_parts),
        title=f"[bold]{file_path}[/bold]  v{v1} → v{v2}",
        box=box.ROUNDED,
        border_style="blue",
    )
    console.print(panel)


def print_history_table(entries: list[dict]) -> None:
    """Print version history for a file.

    Each dict should have: ``version``, ``timestamp``, ``checksum``, ``message``
    """
    if not entries:
        info("No history found.")
        return

    table = Table(
        title="Version History",
        box=box.ROUNDED,
        title_style="bold magenta",
    )
    table.add_column("Version", style="yellow", width=8, justify="center")
    table.add_column("Timestamp", style="cyan", min_width=20)
    table.add_column("Checksum", style="dim", width=12)
    table.add_column("Message", style="white")

    from datetime import datetime, timezone

    for e in entries:
        ts = datetime.fromtimestamp(e["timestamp"], tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        msg = e.get("message") or ""
        table.add_row(
            str(e["version"]),
            ts,
            e["checksum"][:10],
            msg,
        )

    console.print(table)
