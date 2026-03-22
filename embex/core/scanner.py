"""
Scanner — scans the project directory, chunks files, embeds them, and stores in ChromaDB.
"""

import hashlib
import time
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn

from embex.core.chunker import chunk_content
from embex.utils.ignore import should_ignore, get_relative_path, get_folder
from embex.utils.language import detect_language
from embex.utils.display import success, error, info


def _collect_files(project_root, config):
    """Walk the project and return all files that should be processed."""
    files = []
    for path in project_root.rglob("*"):
        if path.is_file() and not should_ignore(path, project_root, config):
            files.append(path)
    return sorted(files)


def scan_project(project_root, config, embedder, vector_store, history_store):
    """Scan the entire project: chunk, embed, and store every eligible file.
    
    Returns a dict with counts: files_processed, chunks_created, errors, files_skipped, files_removed.
    """
    files = _collect_files(project_root, config)
    total_chunks = 0
    errors_count = 0
    skipped_count = 0
    removed_count = 0

    if not files:
        info("No eligible files found to embed.")
        return {"files_processed": 0, "chunks_created": 0, "errors": 0, "files_skipped": 0, "files_removed": 0}

    # Remove vectors for files that were deleted from disk since last scan
    current_rel_paths = {get_relative_path(f, project_root) for f in files}
    for stored_path, stored_folder in history_store.get_all_embed_paths():
        if stored_path not in current_rel_paths:
            vector_store.delete_file(stored_path, stored_folder)
            history_store.delete_embed_checksum(stored_path)
            removed_count += 1

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

                # Skip if file hasn't changed since last embed
                if history_store.get_embed_checksum(rel_path) == checksum:
                    skipped_count += 1
                    progress.advance(task)
                    continue

                # Save snapshot to history
                if config.history.enabled:
                    history_store.snapshot_file(
                        file_path=rel_path,
                        content=content,
                        language=language,
                        folder=folder,
                    )

                # Split into chunks
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

                # Generate embeddings
                embeddings = embedder.embed_texts(chunk_texts)

                # Store in ChromaDB
                metadata_base = {
                    "file_path": rel_path,
                    "folder": folder,
                    "language": language,
                    "last_modified": int(time.time()),
                    "project_root": str(project_root),
                }

                n = vector_store.upsert_file(
                    file_path=rel_path,
                    folder=folder,
                    chunks=chunk_texts,
                    embeddings=embeddings,
                    metadata_base=metadata_base,
                    chunk_metadatas=chunk_line_metas,
                )
                total_chunks += n

                # Save checksum so we can skip unchanged files next time
                history_store.set_embed_checksum(rel_path, checksum, folder)

            except Exception as exc:
                error(f"Failed to process {rel_path}: {exc}")
                errors_count += 1

            progress.advance(task)

    return {
        "files_processed": len(files) - errors_count - skipped_count,
        "chunks_created": total_chunks,
        "errors": errors_count,
        "files_skipped": skipped_count,
        "files_removed": removed_count,
    }
