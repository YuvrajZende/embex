"""
embex diff — show a unified diff between two versions of a file.
"""

from __future__ import annotations

import difflib
from typing import Optional

import typer

from embex.config import find_project_root, history_db_path
from embex.core.history_store import HistoryStore
from embex.utils.display import print_diff, error, info


def diff_command(
    file_path: str = typer.Argument(..., help="Relative path to the file."),
    v1: Optional[int] = typer.Option(None, "--v1", help="First version number (default: second-to-last)."),
    v2: Optional[int] = typer.Option(None, "--v2", help="Second version number (default: latest)."),
) -> None:
    """Show a diff between two versions of a file."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    history_store = HistoryStore(history_db_path(project_root))
    norm_path = file_path.replace("\\", "/")

    latest = history_store.get_latest_version(norm_path)
    if latest == 0:
        error(f"No history found for '{norm_path}'.")
        history_store.close()
        raise typer.Exit(1)

    # Default versions: compare previous vs latest
    version_a = v1 if v1 is not None else max(latest - 1, 1)
    version_b = v2 if v2 is not None else latest

    content_a = history_store.get_snapshot(norm_path, version_a)
    content_b = history_store.get_snapshot(norm_path, version_b)
    history_store.close()

    if content_a is None:
        error(f"Version {version_a} not found for '{norm_path}'.")
        raise typer.Exit(1)
    if content_b is None:
        error(f"Version {version_b} not found for '{norm_path}'.")
        raise typer.Exit(1)

    diff_lines = list(
        difflib.unified_diff(
            content_a.splitlines(),
            content_b.splitlines(),
            fromfile=f"{norm_path} (v{version_a})",
            tofile=f"{norm_path} (v{version_b})",
            lineterm="",
        )
    )

    print_diff(diff_lines, norm_path, version_a, version_b)
