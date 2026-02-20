"""
embex restore — restore a file or an entire folder to a previous version from history.

Usage examples
--------------
# Restore a single file to version 2
embex restore src/auth/login.py --version 2

# Restore a single file to its latest tracked version
embex restore src/auth/login.py

# Restore every tracked file under src/ to its latest version
embex restore src/

# Restore every tracked file under src/ to version 3 (files without that version are skipped)
embex restore src/ --version 3

# Restore ALL tracked files to their latest versions
embex restore . --all
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from embex.config import find_project_root, history_db_path
from embex.core.history_store import HistoryStore
from embex.utils.display import success, error, info, warning


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _restore_single(
    history_store: HistoryStore,
    project_root: Path,
    norm_path: str,
    version: Optional[int],
    *,
    confirm_overwrite: bool = True,
) -> bool:
    """Restore one file.  Returns True on success, False on skip/error."""
    if version is None:
        ver = history_store.get_latest_version(norm_path)
        if ver == 0:
            warning(f"  No history found for '{norm_path}' — skipped.")
            return False
    else:
        ver = version

    content = history_store.get_snapshot(norm_path, ver)
    if content is None:
        warning(f"  Version {ver} not found for '{norm_path}' — skipped.")
        return False

    target = project_root / Path(norm_path)

    # Always recreate missing parent directories.
    target.parent.mkdir(parents=True, exist_ok=True)

    if confirm_overwrite and target.exists():
        confirm = typer.confirm(
            f"Overwrite '{norm_path}' with version {ver}?",
            default=True,
        )
        if not confirm:
            info(f"  Skipped '{norm_path}'.")
            return False

    target.write_text(content, encoding="utf-8")
    history_store.restore_to_version(norm_path, ver)
    return True


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

def restore_command(
    path: str = typer.Argument(
        ...,
        help=(
            "Relative path to a FILE or FOLDER to restore. "
            "Use '.' with --all to restore every tracked file."
        ),
    ),
    version: Optional[int] = typer.Option(
        None,
        "--version",
        "-v",
        help="Version to restore. Defaults to the latest version of each file.",
    ),
    all_files: bool = typer.Option(
        False,
        "--all",
        help="Restore ALL tracked files (use with path '.').",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts (non-interactive / CI mode).",
    ),
) -> None:
    """Restore a file or an entire folder from version history.

    When PATH is a folder prefix (e.g. ``src/``) embex restores every tracked
    file under that folder, recreating any missing directories automatically.
    """
    try:
        project_root = find_project_root()
    except FileNotFoundError:
        error("No Embex project found. Run 'embex init' first.")
        raise typer.Exit(1)

    history_store = HistoryStore(history_db_path(project_root))
    norm_path = path.replace("\\", "/").rstrip("/")

    # ------------------------------------------------------------------
    # Determine whether this is a folder restore or a single-file restore.
    # A path is treated as a folder when:
    #   (a) the user passed --all, OR
    #   (b) the path ends with '/' in the original argument, OR
    #   (c) no snapshot exists for the exact path but snapshots exist whose
    #       paths start with that prefix (i.e. it's a directory prefix).
    # ------------------------------------------------------------------

    is_folder = all_files or path.endswith("/") or path == "."

    if not is_folder:
        # Check: does the exact path exist in history?
        latest = history_store.get_latest_version(norm_path)
        if latest == 0:
            # No exact match — try as a folder prefix.
            candidates = history_store.list_files_in_folder(norm_path)
            if candidates:
                is_folder = True
            else:
                history_store.close()
                error(
                    f"No history found for '{norm_path}'. "
                    "Check the path or run 'embex log' to list tracked files."
                )
                raise typer.Exit(1)

    # ------------------------------------------------------------------
    # Folder restore
    # ------------------------------------------------------------------
    if is_folder:
        if all_files or norm_path == ".":
            files = history_store.list_all_files()
            scope_label = "all tracked files"
        else:
            files = history_store.list_files_in_folder(norm_path)
            scope_label = f"'{norm_path}/' ({len(files)} file(s))"

        if not files:
            history_store.close()
            error("No tracked files found matching that path.")
            raise typer.Exit(1)

        ver_label = f"version {version}" if version is not None else "latest version"
        info(f"Restoring {scope_label} to {ver_label}.")

        if not yes:
            confirm = typer.confirm(
                f"This will recreate {len(files)} file(s) and any missing directories. Continue?",
                default=True,
            )
            if not confirm:
                history_store.close()
                info("Restore cancelled.")
                raise typer.Exit(0)

        restored, skipped = 0, 0
        for fp in files:
            ok = _restore_single(
                history_store,
                project_root,
                fp,
                version,
                confirm_overwrite=False,  # already confirmed above
            )
            if ok:
                success(f"  Restored '{fp}'")
                restored += 1
            else:
                skipped += 1

        history_store.close()
        info(f"Done — {restored} restored, {skipped} skipped.")
        return

    # ------------------------------------------------------------------
    # Single-file restore
    # ------------------------------------------------------------------
    ok = _restore_single(
        history_store,
        project_root,
        norm_path,
        version,
        confirm_overwrite=not yes,
    )
    history_store.close()

    if ok:
        ver_label = f"version {version}" if version is not None else "latest version"
        success(f"Restored '{norm_path}' to {ver_label}.")
    else:
        raise typer.Exit(1)
