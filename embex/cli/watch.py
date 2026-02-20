"""
embex watch — live file watcher that re-embeds on save.

Runs in the foreground, listening for file changes via watchdog.
"""

from __future__ import annotations

import time
from pathlib import Path

import typer
from watchdog.observers import Observer

from embex.config import (
    find_project_root,
    load_config,
    chroma_path,
    history_db_path,
)
from embex.core.embedder import Embedder
from embex.core.vector_store import VectorStore
from embex.core.history_store import HistoryStore
from embex.core.watcher import EmbexEventHandler
from embex.utils.display import success, error, info


def watch_command() -> None:
    """Watch the project for file changes and re-embed automatically."""
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
    history_store = HistoryStore(history_db_path(project_root))

    handler = EmbexEventHandler(
        project_root=project_root,
        config=config,
        embedder=embedder,
        vector_store=vector_store,
        history_store=history_store,
    )

    observer = Observer()
    observer.schedule(handler, str(project_root), recursive=True)
    observer.start()

    success(f"Watching [bold]{project_root}[/bold] for changes...")
    info("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        info("\nStopping watcher...")

    observer.join()
    history_store.close()
    success("Watcher stopped.")
