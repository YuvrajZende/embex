"""
embex ignore — interactively add files/folders to the exclude list.
"""

from __future__ import annotations

import typer

from embex.config import find_project_root, load_config, write_config
from embex.utils.display import console, success, error, info


def ignore_command(
    path: str = typer.Argument(..., help="File pattern or directory to add to the ignore list."),
    is_dir: bool = typer.Option(False, "--dir", "-d", help="Treat the path as a directory to exclude."),
) -> None:
    """Add a file pattern or directory to the Embex exclude list."""
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    config = load_config(project_root)

    if is_dir:
        if path in config.watch.exclude_dirs:
            info(f"'{path}' is already in the exclude directories list.")
            return
        config.watch.exclude_dirs.append(path)
        write_config(project_root, config)
        success(f"Added '{path}' to excluded directories.")
    else:
        if path in config.watch.exclude_files:
            info(f"'{path}' is already in the exclude files list.")
            return
        config.watch.exclude_files.append(path)
        write_config(project_root, config)
        success(f"Added '{path}' to excluded file patterns.")

    # Show current lists
    console.print(f"\n[dim]Excluded dirs:[/dim]  {', '.join(config.watch.exclude_dirs)}")
    console.print(f"[dim]Excluded files:[/dim] {', '.join(config.watch.exclude_files)}")
