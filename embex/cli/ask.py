"""
embex ask — ask a question about your codebase and get an AI-powered answer.

Uses RAG (Retrieval-Augmented Generation) to find relevant code chunks
and sends them to the LLM for a grounded answer with citations.

Usage:
    embex ask "how does authentication work"
    embex ask "where are database queries made" --folder src/db
"""

from typing import Optional
import typer

from embex.config import find_project_root, load_config, chroma_path
from embex.core.embedder import Embedder
from embex.core.vector_store import VectorStore
from embex.core.rag import ask as rag_ask
from embex.utils.display import console, error, info

from rich.markdown import Markdown
from rich.rule import Rule


def ask_command(
    question: str = typer.Argument(..., help="Your question about the codebase."),
    top_k: int = typer.Option(8, "--top-k", "-k", help="Number of chunks to retrieve."),
    folder: Optional[str] = typer.Option(None, "--folder", "-f", help="Limit search to a folder."),
    threshold: float = typer.Option(0.30, "--threshold", "-t", help="Minimum similarity score (0-1)."),
    show_sources: bool = typer.Option(True, "--sources/--no-sources", help="Show source chunks."),
):
    """Ask a question about your codebase — get an AI answer with citations."""
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
    info(f"Searching codebase for: [bold]{question}[/bold]")

    try:
        result = rag_ask(
            question,
            config=config,
            embedder=embedder,
            vector_store=vector_store,
            top_k=top_k,
            folder=folder,
            relevance_threshold=threshold,
        )
    except (EnvironmentError, RuntimeError) as exc:
        error(str(exc))
        raise typer.Exit(1)

    # Show the answer
    console.print()
    console.print(Rule("[bold green]Answer[/bold green]", style="green"))
    console.print(Markdown(result["answer"]))

    # Show the sources
    if show_sources and result["sources"]:
        console.print()
        console.print(Rule("[bold cyan]Sources[/bold cyan]", style="cyan"))
        total = result["total_retrieved"]
        relevant = result["relevant_count"]
        if relevant == 0 and total > 0:
            console.print(f"[dim](all {total} retrieved — none above {threshold:.0%} threshold)[/dim]")
        else:
            console.print(f"[dim]({relevant}/{total} above {threshold:.0%} threshold)[/dim]")
        console.print()

        for src in result["sources"]:
            score_color = "green" if src["score"] >= threshold else "yellow"
            console.print(
                f"  [{score_color}]●[/{score_color}] [bold]{src['file_path']}[/bold] "
                f"chunk #{src['chunk_index']} "
                f"[{score_color}]score={src['score']:.3f}[/{score_color}]"
            )
            preview = src.get("preview", "")
            if preview:
                for line in preview.strip().splitlines()[:3]:
                    console.print(f"    [dim]{line}[/dim]")
            console.print()
