"""
VectorStore — ChromaDB operations for storing and querying code embeddings.

Uses a persistent ChromaDB client stored in ``.embex/chroma/``.
Collections are namespaced by folder path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb


def _collection_name(folder: str) -> str:
    """Convert a folder path into a valid ChromaDB collection name.

    ChromaDB collection names must:
    - be 3-63 chars, start/end with alphanumeric
    - contain only alphanumerics, underscores, hyphens
    """
    if folder in (".", "", "/"):
        return "root"
    name = folder.replace("/", "_").replace("\\", "_")
    # Strip leading/trailing non-alphanumeric characters
    name = name.strip("_-.")
    # Ensure minimum length
    if len(name) < 3:
        name = name + "_col"
    # Truncate to 63
    if len(name) > 63:
        name = name[:63].rstrip("_-")
    return name


class VectorStore:
    """Thin wrapper around a persistent ChromaDB client."""

    def __init__(self, chroma_dir: str | Path) -> None:
        self._chroma_dir = Path(chroma_dir)
        self._chroma_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._chroma_dir))

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def get_or_create_collection(self, folder: str) -> chromadb.Collection:
        """Return (or create) the collection for a given folder path."""
        name = _collection_name(folder)
        return self._client.get_or_create_collection(
            name=name,
            metadata={"folder": folder},
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def upsert_file(
        self,
        file_path: str,
        folder: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata_base: dict[str, Any],
        chunk_metadatas: list[dict[str, Any]] | None = None,
    ) -> int:
        """Delete old chunks for *file_path* and insert new ones.

        Parameters
        ----------
        file_path:
            Relative POSIX path used as the foreign key.
        folder:
            Folder path that determines the collection.
        chunks:
            List of chunk texts.
        embeddings:
            Corresponding embedding vectors.
        metadata_base:
            Shared metadata dict (file_path, language, etc.).

        Returns
        -------
        int
            Number of chunks inserted.
        """
        collection = self.get_or_create_collection(folder)

        # Delete any existing chunks for this file
        self.delete_file(file_path, folder)

        if not chunks:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        embeds: list[list[float]] = []

        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            doc_id = f"{file_path}::{i}"
            meta = {
                **metadata_base,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            if chunk_metadatas and i < len(chunk_metadatas):
                meta.update(chunk_metadatas[i])
            ids.append(doc_id)
            documents.append(chunk_text)
            metadatas.append(meta)
            embeds.append(embedding)

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeds,
            metadatas=metadatas,
        )
        return len(ids)

    def delete_file(self, file_path: str, folder: str) -> None:
        """Remove all chunks belonging to *file_path* from its collection."""
        collection = self.get_or_create_collection(folder)
        # ChromaDB where filter to find all docs with this file_path
        try:
            existing = collection.get(
                where={"file_path": file_path},
            )
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            # Collection might be empty or filter might not match — that's fine
            pass

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def query(
        self,
        query_embedding: list[float],
        folder: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search for the most similar chunks.

        Parameters
        ----------
        query_embedding:
            The embedding vector for the query.
        folder:
            Optional folder to scope the search. If ``None``, searches
            all collections.
        top_k:
            Maximum number of results.

        Returns
        -------
        list[dict]
            Each dict has: ``file_path``, ``chunk_index``, ``score``, ``preview``.
        """
        results: list[dict[str, Any]] = []

        if folder:
            collections = [self.get_or_create_collection(folder)]
        else:
            collections = self._client.list_collections()

        for col in collections:
            try:
                count = col.count()
                if count == 0:
                    continue
                n = min(top_k, count)
                res = col.query(
                    query_embeddings=[query_embedding],
                    n_results=n,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                continue

            if not res["ids"] or not res["ids"][0]:
                continue

            for doc_id, doc, meta, dist in zip(
                res["ids"][0],
                res["documents"][0],
                res["metadatas"][0],
                res["distances"][0],
            ):
                # ChromaDB returns L2 distance by default; lower is better.
                # Convert to a 0-1 similarity score.
                score = 1.0 / (1.0 + dist)
                results.append(
                    {
                        "file_path": meta.get("file_path", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                        "score": score,
                        "preview": (doc or "")[:200],
                        "folder": meta.get("folder", ""),
                        "language": meta.get("language", ""),
                    }
                )

        # Sort by score descending and return top_k
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]
