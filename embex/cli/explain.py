"""
embex explain — use an LLM to summarize what a file does.

Supports two modes:
  - Static analysis (default, free) — extracts imports, functions, classes, docstrings
  - LLM-powered (--llm flag) — sends code to z.ai (GLM models) for a natural language summary
"""

from __future__ import annotations

import typer
from pathlib import Path

from embex.config import find_project_root, load_config, chroma_path
from embex.core.vector_store import VectorStore
from embex.core.embedder import Embedder
from embex.utils.display import console, error, info

from rich.panel import Panel
from rich import box


def _static_analysis(content: str, norm_path: str) -> list[str]:
    """Perform static code analysis and return summary lines."""
    lines = content.split("\n")
    total_lines = len(lines)

    imports = [l.strip() for l in lines if l.strip().startswith(("import ", "from "))]
    functions = [l.strip() for l in lines if l.strip().startswith("def ")]
    classes = [l.strip() for l in lines if l.strip().startswith("class ")]

    parts = []
    parts.append(f"[bold cyan]File:[/bold cyan] {norm_path}")
    parts.append(f"[bold cyan]Total lines:[/bold cyan] {total_lines}")

    if imports:
        parts.append(f"\n[bold yellow]Dependencies ({len(imports)}):[/bold yellow]")
        for imp in imports[:10]:
            parts.append(f"  [dim]•[/dim] {imp}")
        if len(imports) > 10:
            parts.append(f"  [dim]... and {len(imports) - 10} more[/dim]")

    if classes:
        parts.append(f"\n[bold magenta]Classes ({len(classes)}):[/bold magenta]")
        for cls in classes:
            parts.append(f"  [dim]•[/dim] {cls}")

    if functions:
        parts.append(f"\n[bold green]Functions ({len(functions)}):[/bold green]")
        for fn in functions:
            parts.append(f"  [dim]•[/dim] {fn}")

    # Docstrings
    docstrings = _extract_docstrings(lines)
    if docstrings:
        parts.append(f"\n[bold blue]Purpose:[/bold blue]")
        for doc in docstrings[:3]:
            if doc:
                parts.append(f"  {doc[:200]}")

    return parts


def _extract_docstrings(lines: list[str]) -> list[str]:
    """Extract module/class/function docstrings."""
    docstrings = []
    in_docstring = False
    current_doc: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if in_docstring:
                current_doc.append(stripped.rstrip("\"'"))
                docstrings.append(" ".join(current_doc).strip())
                current_doc = []
                in_docstring = False
            elif stripped.count('"""') == 2 or stripped.count("'''") == 2:
                doc = stripped.strip("\"'").strip()
                if doc:
                    docstrings.append(doc)
            else:
                in_docstring = True
                current_doc = [stripped.lstrip("\"'").lstrip("'")]
        elif in_docstring:
            current_doc.append(stripped)
    return docstrings


def _llm_explain(content: str, norm_path: str, config=None, model: str = None) -> str:
    """Use the z.ai LLM to generate a natural language explanation of the file."""
    import os
    from pathlib import Path as _Path
    from dotenv import load_dotenv

    load_dotenv()  # project-local .env
    load_dotenv(dotenv_path=_Path.home() / ".embex" / ".env", override=False)  # global fallback

    cfg_model = config.llm.model if config else "glm-4.7-flash"
    cfg_api_key_env = config.llm.api_key_env if config else "ZAI_API_KEY"

    final_model = model or cfg_model
    api_key = os.environ.get(cfg_api_key_env, "")

    if not api_key:
        return f"[red]Error:[/red] {cfg_api_key_env} not found. Set it in your .env file or environment."

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.z.ai/api/paas/v4/",
        )

        # GLM models support large context; cap at 12 000 chars to be safe
        max_chars = 12_000
        truncated = content[:max_chars]
        if len(content) > max_chars:
            truncated += f"\n\n... (truncated, {len(content)} total chars)"

        response = client.chat.completions.create(
            model=final_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior software engineer. Explain what the given code file does "
                        "in clear, concise language. Cover: purpose, key functions/classes, "
                        "dependencies, and how it fits into a larger project. "
                        "Keep your response under 300 words. Use bullet points."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Explain this file ({norm_path}):\n\n```\n{truncated}\n```",
                },
            ],
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=500,
            temperature=0.7,
        )

        msg = response.choices[0].message
        result = msg.content or getattr(msg, "reasoning_content", None) or "No response generated."
        return result

    except Exception as e:
        return f"[red]LLM Error (z.ai):[/red] {e}"


def explain_command(
    file_path: str = typer.Argument(..., help="Relative path to the file to explain."),
    llm: bool = typer.Option(False, "--llm", "-l", help="Use LLM for a richer explanation."),
    model: str = typer.Option(None, "--model", "-m", help="Override GLM model name (e.g. glm-4-flash, glm-4)."),
) -> None:
    """Summarize what a file does — static analysis or LLM-powered (z.ai)."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    config = load_config(project_root)
    norm_path = file_path.replace("\\", "/")

    full_path = project_root / norm_path
    if not full_path.exists():
        error(f"File not found: {norm_path}")
        raise typer.Exit(1)

    content = full_path.read_text(encoding="utf-8", errors="replace")

    if not content.strip():
        info(f"File '{norm_path}' is empty.")
        raise typer.Exit(0)

    # Static analysis
    summary_parts = _static_analysis(content, norm_path)

    # Find related files via embeddings
    try:
        embedder = Embedder(config)
        vector_store = VectorStore(chroma_path(project_root))
        query_embedding = embedder.embed_query(content[:500])
        related = vector_store.query(query_embedding=query_embedding, top_k=3)

        if related:
            summary_parts.append(f"\n[bold white]Related files:[/bold white]")
            seen = set()
            for r in related:
                rp = r["file_path"]
                if rp != norm_path and rp not in seen:
                    seen.add(rp)
                    summary_parts.append(f"  [dim]•[/dim] {rp} (similarity: {r['score']:.3f})")
    except Exception:
        pass  # Non-critical — skip if embeddings fail

    # LLM explanation
    if llm:
        final_model = model or config.llm.model
        summary_parts.append(f"\n[bold cyan]═══ LLM Analysis (z.ai:{final_model}) ═══[/bold cyan]")
        llm_result = _llm_explain(content, norm_path, config, model)
        summary_parts.append(llm_result)

    console.print(Panel(
        "\n".join(summary_parts),
        title=f"[bold]Explanation: {norm_path}[/bold]",
        box=box.ROUNDED,
    ))
