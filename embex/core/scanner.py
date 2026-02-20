"""
Scanner — initial full-project scan, chunk, embed, and store.

Walks the project directory tree, respects ignore rules, and processes
every eligible file through the chunk → embed → store pipeline.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
)

from embex.core.chunker import chunk_content
from embex.core.smart_chunker import smart_chunk
from embex.core.auto_tagger import apply_tags_to_metadata
from embex.utils.ignore import should_ignore, get_relative_path, get_folder
from embex.utils.language import detect_language
from embex.utils.display import success, error, info

if TYPE_CHECKING:
    from embex.config import EmbexConfig
    from embex.core.embedder import Embedder
    from embex.core.vector_store import VectorStore
    from embex.core.history_store import HistoryStore


def _collect_files(project_root: Path, config: "EmbexConfig") -> list[Path]:
    """Walk the project tree and return all eligible file paths."""
    files: list[Path] = []
    for path in project_root.rglob("*"):
        if path.is_file() and not should_ignore(path, project_root, config):
            files.append(path)
    return sorted(files)


def scan_project(
    project_root: Path,
    config: "EmbexConfig",
    embedder: "Embedder",
    vector_store: "VectorStore",
    history_store: "HistoryStore",
) -> dict[str, int]:
    """Scan the entire project: chunk, embed, and store every eligible file.

    Returns
    -------
    dict[str, int]
        Summary with keys: ``files_processed``, ``chunks_created``, ``errors``.
    """
    files = _collect_files(project_root, config)
    total_chunks = 0
    errors_count = 0
    skipped_count = 0

    if not files:
        info("No eligible files found to embed.")
        return {"files_processed": 0, "chunks_created": 0, "errors": 0, "files_skipped": 0}

    info(f"Found {len(files)} file(s) to process.")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("Embedding files...", total=len(files))

        for file_path in files:
            rel_path = get_relative_path(file_path, project_root)
            folder = get_folder(file_path, project_root)
            language = detect_language(file_path)

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # Skip re-embedding if content hasn't changed since last embed.
                if history_store.get_embed_checksum(rel_path) == checksum:
                    skipped_count += 1
                    progress.advance(task)
                    continue

                # Snapshot to history
                if config.history.enabled:
                    history_store.snapshot_file(
                        file_path=rel_path,
                        content=content,
                        language=language,
                        folder=folder,
                    )

                # Chunk — use AST-based smart chunking or fixed-size
                if config.chunking.strategy == "ast":
                    ext = file_path.suffix.lower()
                    smart_chunks = smart_chunk(content, ext, config)
                    if not smart_chunks:
                        progress.advance(task)
                        continue
                    chunk_texts = [c.text for c in smart_chunks]
                    chunk_line_metas = [
                        {"start_line": c.start_line, "end_line": c.end_line}
                        for c in smart_chunks
                    ]
                else:
                    raw_chunks = chunk_content(
                        content,
                        chunk_size=config.chunking.chunk_size,
                        overlap=config.chunking.overlap,
                    )
                    if not raw_chunks:
                        progress.advance(task)
                        continue
                    chunk_texts = [text for text, _, _, _ in raw_chunks]
                    chunk_line_metas = [
                        {"start_line": s, "end_line": e}
                        for _, _, s, e in raw_chunks
                    ]

                # Embed
                embeddings = embedder.embed_texts(chunk_texts)

                # Store in ChromaDB
                metadata_base = {
                    "file_path": rel_path,
                    "folder": folder,
                    "language": language,
                    "last_modified": int(time.time()),
                    "project_root": str(project_root),
                }

                # Merge auto-tag metadata with per-chunk line info
                chunk_metadatas = []
                for i, ct in enumerate(chunk_texts):
                    meta = apply_tags_to_metadata(dict(metadata_base), ct)
                    if i < len(chunk_line_metas):
                        meta.update(chunk_line_metas[i])
                    chunk_metadatas.append(meta)

                n = vector_store.upsert_file(
                    file_path=rel_path,
                    folder=folder,
                    chunks=chunk_texts,
                    embeddings=embeddings,
                    metadata_base=metadata_base,
                    chunk_metadatas=chunk_metadatas,
                )
                total_chunks += n

                # Record the checksum so we can skip this file next time.
                history_store.set_embed_checksum(rel_path, checksum)

            except Exception as exc:
                error(f"Failed to process {rel_path}: {exc}")
                errors_count += 1

            progress.advance(task)

    return {
        "files_processed": len(files) - errors_count - skipped_count,
        "chunks_created": total_chunks,
        "errors": errors_count,
        "files_skipped": skipped_count,
    }
