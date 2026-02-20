"""
Ignore-rules engine — decide whether a file should be skipped.

Checks against the exclude_dirs, exclude_files, and include_extensions
lists defined in EmbexConfig.watch.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from embex.config import EmbexConfig


def should_ignore(file_path: str | Path, project_root: str | Path, config: "EmbexConfig") -> bool:
    """Return ``True`` if *file_path* should be skipped based on config rules.

    Parameters
    ----------
    file_path:
        Absolute or relative path to the file.
    project_root:
        The project root directory (used to compute relative paths).
    config:
        Loaded EmbexConfig instance.
    """
    path = Path(file_path).resolve()
    root = Path(project_root).resolve()

    # Compute relative path using forward slashes for consistent matching
    try:
        rel = path.relative_to(root)
    except ValueError:
        # File is outside project — ignore it
        return True

    rel_posix = PurePosixPath(rel)
    watch = config.watch

    # 1. Check exclude_dirs — any directory component matches?
    for part in rel_posix.parts[:-1]:  # all but the filename
        if part in watch.exclude_dirs:
            return True

    # 2. Check exclude_files — filename glob patterns
    filename = rel_posix.name
    for pattern in watch.exclude_files:
        if fnmatch.fnmatch(filename, pattern):
            return True

    # 3. Check include_extensions — file must have an allowed extension
    ext = path.suffix.lower()
    if ext not in watch.include_extensions:
        return True

    return False


def get_relative_path(file_path: str | Path, project_root: str | Path) -> str:
    """Return the POSIX-style relative path of *file_path* from *project_root*."""
    path = Path(file_path).resolve()
    root = Path(project_root).resolve()
    return PurePosixPath(path.relative_to(root)).as_posix()


def get_folder(file_path: str | Path, project_root: str | Path) -> str:
    """Return the folder portion of the relative path (or ``'.'`` for root)."""
    rel = get_relative_path(file_path, project_root)
    parts = rel.split("/")
    if len(parts) <= 1:
        return "."
    return "/".join(parts[:-1])
