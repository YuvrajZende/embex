"""
embex query — semantic search across the embedded codebase.
"""

from __future__ import annotations

from typing import Optional

import typer

from embex.config import find_project_root, load_config, chroma_path
from embex.core.embedder import Embedder
from embex.core.vector_store import VectorStore
from embex.utils.display import print_results_table, error


def query_command(
    question: str = typer.Argument(..., help="Natural language query to search for."),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results to return."),
    folder: Optional[str] = typer.Option(None, "--folder", "-f", help="Scope search to a specific folder."),
) -> None:
    """Search the codebase semantically."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    config = load_config(project_root)

    try:
        embedder = Embedder(config)
    except EnvironmentError as exc:
        error(str(exc))
        raise typer.Exit(1)

    vector_store = VectorStore(chroma_path(project_root))

    # Embed the query
    query_embedding = embedder.embed_query(question)

    # Search
    results = vector_store.query(
        query_embedding=query_embedding,
        folder=folder,
        top_k=top_k,
    )

    print_results_table(results)
