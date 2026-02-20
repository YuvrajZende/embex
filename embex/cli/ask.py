"""
embex ask — CRAG-powered Q&A over your codebase.

Retrieves the most relevant code chunks, filters for relevance, then
sends them to the configured LLM (OpenAI / Groq / Ollama) to produce
a grounded natural-language answer — with citations back to source files.

Usage:
    embex ask "how does authentication work"
    embex ask "where are database queries made" --folder src/db
    embex ask "explain the chunking strategy" --top-k 10 --no-stream
"""

from __future__ import annotations

from typing import Optional

import typer

from embex.config import find_project_root, load_config, chroma_path
from embex.core.embedder import Embedder
from embex.core.vector_store import VectorStore
from embex.core.rag import ask as rag_ask
from embex.utils.display import console, error, info

from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich import box


def ask_command(
    question: str = typer.Argument(..., help="Natural language question about your codebase."),
    top_k: int = typer.Option(8, "--top-k", "-k", help="Number of chunks to retrieve initially."),
    folder: Optional[str] = typer.Option(None, "--folder", "-f", help="Scope search to a specific folder."),
    threshold: float = typer.Option(0.30, "--threshold", "-t", help="Minimum similarity score (0-1) for relevance."),
    show_sources: bool = typer.Option(True, "--sources/--no-sources", help="Show retrieved source chunks."),
) -> None:
    """Ask a question about your codebase — get a grounded LLM answer with citations."""
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
    except EnvironmentError as exc:
        error(str(exc))
        raise typer.Exit(1)
    except RuntimeError as exc:
        error(str(exc))
        raise typer.Exit(1)

    # ── Display answer ──────────────────────────────────────────────────
    console.print()
    console.print(Rule("[bold green]Answer[/bold green]", style="green"))
    console.print(Markdown(result["answer"]))

    # ── Display sources ─────────────────────────────────────────────────
    if show_sources and result["sources"]:
        console.print()
        console.print(Rule("[bold cyan]Sources[/bold cyan]", style="cyan"))
        total = result["total_retrieved"]
        relevant = result["relevant_count"]
        fallback_note = (
            f"[dim](all {total} retrieved — none cleared the {threshold:.0%} threshold)[/dim]"
            if relevant == 0 and total > 0
            else f"[dim]({relevant}/{total} above {threshold:.0%} threshold)[/dim]"
        )
        console.print(fallback_note)
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
                preview_lines = preview.strip().splitlines()[:3]
                for line in preview_lines:
                    console.print(f"    [dim]{line}[/dim]")
            console.print()
