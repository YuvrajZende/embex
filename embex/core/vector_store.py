"""
VectorStore — stores and queries code embeddings using ChromaDB.
"""

from pathlib import Path
import chromadb


def _collection_name(folder):
    """Convert a folder path to a valid ChromaDB collection name."""
    if folder in (".", "", "/"):
        return "root"
    name = folder.replace("/", "_").replace("\\", "_")
    name = name.strip("_-.")
    if len(name) < 3:
        name = name + "_col"
    if len(name) > 63:
        name = name[:63].rstrip("_-")
    return name


class VectorStore:
    """Wrapper around ChromaDB for storing and searching code chunk embeddings."""

    def __init__(self, chroma_dir):
        self.chroma_dir = Path(chroma_dir)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.chroma_dir))

    def get_or_create_collection(self, folder):
        """Get or create a ChromaDB collection for the given folder."""
        name = _collection_name(folder)
        return self._client.get_or_create_collection(
            name=name,
            metadata={"folder": folder},
        )

    def upsert_file(self, file_path, folder, chunks, embeddings, metadata_base, chunk_metadatas=None):
        """Delete old chunks for a file and insert new ones. Returns number of chunks inserted."""
        collection = self.get_or_create_collection(folder)

        # Remove existing chunks for this file first
        self.delete_file(file_path, folder)

        if not chunks:
            return 0

        ids = []
        documents = []
        metadatas = []
        embeds = []

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

    def delete_file(self, file_path, folder):
        """Remove all chunks for a file from its collection."""
        collection = self.get_or_create_collection(folder)
        try:
            existing = collection.get(where={"file_path": file_path})
            if existing["ids"]:
                collection.delete(ids=existing["ids"])
        except Exception:
            pass  # collection might be empty

    def query(self, query_embedding, folder=None, top_k=5):
        """Search for the most similar chunks. Returns a list of result dicts."""
        results = []

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
                # Convert L2 distance to similarity score (0-1, higher = better)
                score = 1.0 / (1.0 + dist)
                results.append({
                    "file_path": meta.get("file_path", ""),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": score,
                    "preview": (doc or "")[:200],
                    "folder": meta.get("folder", ""),
                    "language": meta.get("language", ""),
                })

        # Sort by score (best matches first)
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]
