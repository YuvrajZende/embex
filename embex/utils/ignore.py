"""
Ignore rules — decides if a file should be skipped during scanning.
"""

import fnmatch
from pathlib import Path, PurePosixPath


def should_ignore(file_path, project_root, config):
    """Check if a file should be ignored based on config rules."""
    path = Path(file_path).resolve()
    root = Path(project_root).resolve()

    # Get relative path
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True  # file is outside project

    rel_posix = PurePosixPath(rel)
    watch = config.watch

    # Check if any parent directory is excluded
    for part in rel_posix.parts[:-1]:
        if part in watch.exclude_dirs:
            return True

    # Check if filename matches any exclude pattern
    filename = rel_posix.name
    for pattern in watch.exclude_files:
        if fnmatch.fnmatch(filename, pattern):
            return True

    # Check if file extension is in the allowed list
    ext = path.suffix.lower()
    if ext not in watch.include_extensions:
        return True

    return False


def get_relative_path(file_path, project_root):
    """Get the relative path of a file from the project root (forward slashes)."""
    path = Path(file_path).resolve()
    root = Path(project_root).resolve()
    return PurePosixPath(path.relative_to(root)).as_posix()


def get_folder(file_path, project_root):
    """Get just the folder part of the relative path (or '.' for root files)."""
    rel = get_relative_path(file_path, project_root)
    parts = rel.split("/")
    if len(parts) <= 1:
        return "."
    return "/".join(parts[:-1])
