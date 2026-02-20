"""
embex similar — find files that are semantically similar to a given file.
"""

from __future__ import annotations

import typer

from embex.config import find_project_root, load_config, chroma_path
from embex.core.embedder import Embedder
from embex.core.vector_store import VectorStore
from embex.utils.display import console, error

from rich.table import Table
from rich import box


def similar_command(
    file_path: str = typer.Argument(..., help="Relative path to the file to find similar files for."),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of similar chunks to return."),
) -> None:
    """Find files that are semantically similar to a given file (detect duplicate logic)."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    config = load_config(project_root)
    norm_path = file_path.replace("\\", "/")

    # Read the file
    full_path = project_root / norm_path
    if not full_path.exists():
        error(f"File not found: {norm_path}")
        raise typer.Exit(1)

    content = full_path.read_text(encoding="utf-8", errors="replace")

    embedder = Embedder(config)
    vector_store = VectorStore(chroma_path(project_root))

    # Embed the file content and search
    query_embedding = embedder.embed_query(content[:1000])
    results = vector_store.query(
        query_embedding=query_embedding,
        top_k=top_k + 5,  # Get extra to filter out self-matches
    )

    # Filter out chunks from the same file
    similar = [r for r in results if r["file_path"] != norm_path][:top_k]

    if not similar:
        console.print(f"[yellow]No similar files found for '{norm_path}'.[/yellow]")
        return

    table = Table(
        title=f"Files similar to {norm_path}",
        box=box.ROUNDED,
        title_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan", min_width=30)
    table.add_column("Language", style="green", width=12)
    table.add_column("Score", style="yellow", width=8, justify="right")
    table.add_column("Preview", style="dim", max_width=50)

    for i, r in enumerate(similar, 1):
        table.add_row(
            str(i),
            r["file_path"],
            r.get("language", "?"),
            f"{r['score']:.4f}",
            r["preview"][:50],
        )

    console.print(table)
