"""
embex search — search for code patterns (literal or regex) in the embedded codebase.
"""

from typing import Optional
import typer
import re

from embex.config import find_project_root, load_config, chroma_path
from embex.core.vector_store import VectorStore
from embex.utils.display import console, error

from rich.table import Table
from rich import box


def search_command(
    pattern: str = typer.Argument(..., help="Code pattern to search for."),
    folder: Optional[str] = typer.Option(None, "--folder", "-f", help="Limit search to a folder."),
    regex: bool = typer.Option(False, "--regex", "-r", help="Treat pattern as regex."),
    top_k: int = typer.Option(20, "--top-k", "-k", help="Max results to return."),
):
    """Search for a code pattern (literal or regex) in your codebase."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    vector_store = VectorStore(chroma_path(project_root))
    collections = vector_store._client.list_collections()

    # Compile regex pattern if needed
    if regex:
        try:
            pat = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            error(f"Invalid regex: {e}")
            raise typer.Exit(1)
    else:
        pat = None

    matches = []
    seen = set()

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

            # Check if the pattern matches
            if pat:
                match = pat.search(doc)
            else:
                match = pattern.lower() in doc.lower()

            if match:
                # Find the matching line and its line number
                lines = doc.split("\n")
                preview_line = ""
                matched_offset = 0

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
                    abs_line = 0
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
                        "preview": preview_line[:120] if preview_line else doc[:120].strip(),
                    })

                if len(matches) >= top_k:
                    break

    if not matches:
        console.print(f"[yellow]No matches found for: {pattern}[/yellow]")
        return

    # Display results in a table
    table = Table(title=f"Code Search: '{pattern}'", box=box.ROUNDED, title_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan", min_width=30)
    table.add_column("Lines", style="yellow", width=12, justify="right")
    table.add_column("Preview", style="white")

    for i, m in enumerate(matches, 1):
        file_col = f"{m['file_path']}{m['line_ref']}"
        start = m.get("start_line")
        end = m.get("end_line")
        lines_col = f"{start}–{end}" if start and end else "—"
        table.add_row(str(i), file_col, lines_col, m["preview"])

    console.print(table)
    console.print(f"\n[dim]{len(matches)} match(es) found.[/dim]")
