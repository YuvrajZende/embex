"""
Watcher — watches for file changes using watchdog and re-embeds them automatically.
"""

import time
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler

from embex.core.chunker import chunk_content
from embex.utils.ignore import should_ignore, get_relative_path, get_folder
from embex.utils.language import detect_language
from embex.utils.display import success, error, info

# How many seconds to wait before processing the same file again
DEBOUNCE_SECONDS = 1.0


class EmbexEventHandler(FileSystemEventHandler):
    """Handles file system events and updates embeddings when files change."""

    def __init__(self, project_root, config, embedder, vector_store, history_store):
        super().__init__()
        self.project_root = project_root.resolve()
        self.config = config
        self.embedder = embedder
        self.vector_store = vector_store
        self.history_store = history_store
        self.last_event_time = {}  # tracks when each file was last processed
        self.lock = threading.Lock()

    def _is_debounced(self, path):
        """Check if we should skip this event (too soon after the last one)."""
        now = time.time()
        with self.lock:
            last = self.last_event_time.get(path, 0)
            if now - last < DEBOUNCE_SECONDS:
                return True
            self.last_event_time[path] = now
            return False

    def _process_file(self, file_path):
        """Read a file, chunk it, embed chunks, and store them."""
        rel_path = get_relative_path(file_path, self.project_root)
        folder = get_folder(file_path, self.project_root)
        language = detect_language(file_path)

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")

            # Save to history
            if self.config.history.enabled:
                self.history_store.snapshot_file(
                    file_path=rel_path,
                    content=content,
                    language=language,
                    folder=folder,
                )

            # Split into chunks
            raw_chunks = chunk_content(
                content,
                chunk_size=self.config.chunking.chunk_size,
                overlap=self.config.chunking.overlap,
            )

            if not raw_chunks:
                info(f"  {rel_path} — empty or no chunks")
                return

            chunk_texts = [text for text, _, _, _ in raw_chunks]
            chunk_line_metas = [
                {"start_line": s, "end_line": e}
                for _, _, s, e in raw_chunks
            ]

            # Generate embeddings
            embeddings = self.embedder.embed_texts(chunk_texts)

            # Store in vector database
            metadata_base = {
                "file_path": rel_path,
                "folder": folder,
                "language": language,
                "last_modified": int(time.time()),
                "project_root": str(self.project_root),
            }
            n = self.vector_store.upsert_file(
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

    def _handle_event(self, event):
        """Common handler for file create/modify events."""
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if should_ignore(file_path, self.project_root, self.config):
            return
        if self._is_debounced(str(file_path)):
            return
        self._process_file(file_path)

    def on_created(self, event):
        self._handle_event(event)

    def on_modified(self, event):
        self._handle_event(event)

    def on_deleted(self, event):
        """When a file is deleted, remove its embeddings."""
        if event.is_directory:
            return
        file_path = Path(event.src_path)
        if should_ignore(file_path, self.project_root, self.config):
            return
        rel_path = get_relative_path(file_path, self.project_root)
        folder = get_folder(file_path, self.project_root)
        try:
            self.vector_store.delete_file(rel_path, folder)
            info(f"Removed embeddings for deleted file: {rel_path}")
        except Exception as exc:
            error(f"Failed to clean up {rel_path}: {exc}")
