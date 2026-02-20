"""
Watcher — file system event handler using watchdog.

Watches for file creates, modifications, and deletions, then runs the
chunk → embed → upsert pipeline for each changed file.
"""

from __future__ import annotations

import time
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import FileSystemEventHandler, FileSystemEvent

from embex.core.chunker import chunk_content
from embex.utils.ignore import should_ignore, get_relative_path, get_folder
from embex.utils.language import detect_language
from embex.utils.display import success, error, info

if TYPE_CHECKING:
    from embex.config import EmbexConfig
    from embex.core.embedder import Embedder
    from embex.core.vector_store import VectorStore
    from embex.core.history_store import HistoryStore


# Debounce window in seconds — ignore rapid successive events on the same file
_DEBOUNCE_SECONDS = 1.0


class EmbexEventHandler(FileSystemEventHandler):
    """Handle file system events and update embeddings."""

    def __init__(
        self,
        project_root: Path,
        config: "EmbexConfig",
        embedder: "Embedder",
        vector_store: "VectorStore",
        history_store: "HistoryStore",
    ) -> None:
        super().__init__()
        self._project_root = project_root.resolve()
        self._config = config
        self._embedder = embedder
        self._vector_store = vector_store
        self._history_store = history_store
        self._last_event: dict[str, float] = {}
        self._lock = threading.Lock()

    def _is_debounced(self, path: str) -> bool:
        """Return True if we should skip this event (too soon after last one)."""
        now = time.time()
        with self._lock:
            last = self._last_event.get(path, 0)
            if now - last < _DEBOUNCE_SECONDS:
                return True
            self._last_event[path] = now
            return False

    def _process_file(self, file_path: Path) -> None:
        """Read → snapshot → chunk → embed → upsert a single file."""
        rel_path = get_relative_path(file_path, self._project_root)
        folder = get_folder(file_path, self._project_root)
        language = detect_language(file_path)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")

            # History snapshot
            if self._config.history.enabled:
                version = self._history_store.snapshot_file(
                    file_path=rel_path,
                    content=content,
                    language=language,
                    folder=folder,
                )
            else:
                version = 0

            # Chunk
            raw_chunks = chunk_content(
                content,
                chunk_size=self._config.chunking.chunk_size,
                overlap=self._config.chunking.overlap,
            )

            if not raw_chunks:
                info(f"  {rel_path} — empty/no chunks")
                return

            chunk_texts = [text for text, _, _, _ in raw_chunks]
            chunk_line_metas = [
                {"start_line": s, "end_line": e}
                for _, _, s, e in raw_chunks
            ]

            # Embed
            embeddings = self._embedder.embed_texts(chunk_texts)

            # Upsert
            metadata_base = {
                "file_path": rel_path,
                "folder": folder,
                "language": language,
                "last_modified": int(time.time()),
                "version": version,
                "project_root": str(self._project_root),
            }
            n = self._vector_store.upsert_file(
                file_path=rel_path,
                folder=folder,
                chunks=chunk_texts,
                embeddings=embeddings,
                metadata_base=metadata_base,
                chunk_metadatas=chunk_line_metas,
            )
            success(f"Embedded {rel_path} — {n} chunk(s)")

        except Exception as exc:
            error(f"Failed to process {rel_path}: {exc}")

    def _handle_event(self, event: FileSystemEvent) -> None:
        """Common handler for create/modify events."""
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if should_ignore(file_path, self._project_root, self._config):
            return
        if self._is_debounced(str(file_path)):
            return
        self._process_file(file_path)

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle_event(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle_event(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if should_ignore(file_path, self._project_root, self._config):
            return
        rel_path = get_relative_path(file_path, self._project_root)
        folder = get_folder(file_path, self._project_root)
        try:
            self._vector_store.delete_file(rel_path, folder)
            info(f"Removed embeddings for deleted file: {rel_path}")
        except Exception as exc:
            error(f"Failed to clean up {rel_path}: {exc}")
