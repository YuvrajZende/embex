"""
Display helpers — pretty print messages and tables using Rich.
"""

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()
error_console = Console(stderr=True)


def success(message: str) -> None:
    """Print a green success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def error(message: str) -> None:
    """Print a red error message."""
    error_console.print(f"[bold red]✗[/bold red] {message}")


def info(message: str) -> None:
    """Print a blue info message."""
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


def warning(message: str) -> None:
    """Print a yellow warning message."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_results_table(results: list[dict]) -> None:
    """Print search results in a nice table format."""
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
