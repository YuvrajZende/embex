"""
embex search — search by code pattern (regex or literal).
"""

from __future__ import annotations

from typing import Optional

import typer

from embex.config import find_project_root, load_config, chroma_path
from embex.core.vector_store import VectorStore
from embex.utils.display import console, error

from rich.table import Table
from rich import box
import re


def search_command(
    pattern: str = typer.Argument(..., help="Code pattern to search for (supports regex)."),
    folder: Optional[str] = typer.Option(None, "--folder", "-f", help="Scope search to a folder."),
    regex: bool = typer.Option(False, "--regex", "-r", help="Treat pattern as regex."),
    top_k: int = typer.Option(20, "--top-k", "-k", help="Max results to return."),
) -> None:
    """Search by code pattern (literal or regex)."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    vector_store = VectorStore(chroma_path(project_root))
    collections = vector_store._client.list_collections()

    if regex:
        try:
            pat = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            error(f"Invalid regex: {e}")
            raise typer.Exit(1)
    else:
        pat = None

    matches: list[dict] = []
    seen: set[tuple] = set()

    for col in collections:
        col_folder = col.metadata.get("folder", "") if col.metadata else ""
        if folder and col_folder != folder:
            continue

        try:
            all_docs = col.get(include=["documents", "metadatas"])
        except Exception:
            continue

        if not all_docs["documents"]:
            continue

        for doc, meta in zip(all_docs["documents"], all_docs["metadatas"]):
            if not doc:
                continue

            if pat:
                match = pat.search(doc)
            else:
                match = pattern.lower() in doc.lower()

            if match:
                # Find the matching line and compute its absolute file line number
                lines = doc.split("\n")
                preview_line = ""
                matched_offset = 0  # 0-based offset within chunk lines
                for j, line in enumerate(lines):
                    if pat:
                        if pat.search(line):
                            preview_line = line.strip()
                            matched_offset = j
                            break
                    else:
                        if pattern.lower() in line.lower():
                            preview_line = line.strip()
                            matched_offset = j
                            break

                start_line = meta.get("start_line")
                if start_line is not None:
                    abs_line = start_line + matched_offset
                    line_ref = f":{abs_line}"
                else:
                    line_ref = ""

                fp = meta.get("file_path", "?")
                dedup_key = (fp, abs_line if start_line is not None else meta.get("chunk_index", 0))
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    matches.append({
                        "file_path": fp,
                        "line_ref": line_ref,
                        "start_line": start_line,
                        "end_line": meta.get("end_line"),
                        "chunk_index": meta.get("chunk_index", 0),
                        "folder": meta.get("folder", ""),
                        "language": meta.get("language", ""),
                        "preview": preview_line[:120] if preview_line else doc[:120].strip(),
                    })

                if len(matches) >= top_k:
                    break

    if not matches:
        console.print(f"[yellow]No matches found for pattern: {pattern}[/yellow]")
        return

    table = Table(title=f"Code Search: '{pattern}'", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan", min_width=30)
    table.add_column("Lines", style="yellow", width=12, justify="right")
    table.add_column("Preview", style="white")

    for i, m in enumerate(matches, 1):
        file_col = f"{m['file_path']}{m['line_ref']}"
        start = m.get("start_line")
        end   = m.get("end_line")
        lines_col = f"{start}–{end}" if start and end else "—"
        table.add_row(str(i), file_col, lines_col, m["preview"])

    console.print(table)
    console.print(f"\n[dim]{len(matches)} match(es) found.[/dim]")
