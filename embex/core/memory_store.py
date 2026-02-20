"""
Agent Memory Store — persistent, searchable memory for LLM agents.

Agents (Cursor, Claude Desktop, custom scripts) can use this to:
  - ``remember(text)``  — store a fact, note, or decision in vector memory.
  - ``recall(query)``   — retrieve the most relevant memories semantically.
  - ``list_memories()`` — list all stored memories.
  - ``forget(id)``      — delete a specific memory by ID.

Storage:
  - SQLite  (.embex/memory.db)  — metadata, text, and timestamps.
  - ChromaDB (.embex/chroma/)   — embeddings for semantic recall.
    Uses a dedicated "agent_memory" collection, isolated from code chunks.

This is intentionally separate from the code vector store so agent memories
never pollute semantic code search results.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryStore:
    """Persistent semantic memory store for AI agents."""

    _COLLECTION_NAME = "agent_memory"

    def __init__(self, db_path: str | Path, chroma_dir: str | Path) -> None:
        """
        Parameters
        ----------
        db_path:
            Path to the SQLite file (e.g. ``.embex/memory.db``).
        chroma_dir:
            Path to the ChromaDB directory (e.g. ``.embex/chroma/``).
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

        import chromadb
        self._chroma = chromadb.PersistentClient(path=str(chroma_dir))
        self._collection = self._chroma.get_or_create_collection(
            name=self._COLLECTION_NAME,
            metadata={"description": "Agent memory store"},
        )

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id          TEXT PRIMARY KEY,
                content     TEXT NOT NULL,
                tags        TEXT DEFAULT '',
                agent       TEXT DEFAULT '',
                created_at  INTEGER NOT NULL,
                checksum    TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_memories_agent   ON memories(agent);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def remember(
        self,
        content: str,
        *,
        embedder,
        tags: list[str] | None = None,
        agent: str = "",
    ) -> str:
        """Store a new memory and return its ID.

        Parameters
        ----------
        content:
            The text to remember (fact, decision, note, etc.).
        embedder:
            An initialised ``Embedder`` instance from embex.core.embedder.
        tags:
            Optional list of string tags for filtering.
        agent:
            Optional agent identifier (e.g. "cursor", "claude-desktop").

        Returns
        -------
        str
            The unique memory ID.
        """
        memory_id = str(uuid.uuid4())
        checksum = hashlib.sha1(content.encode()).hexdigest()
        tags_str = ",".join(tags or [])
        created_at = int(time.time())

        # Embed
        embedding = embedder.embed_texts([content])[0]

        # SQLite
        self._conn.execute(
            "INSERT INTO memories (id, content, tags, agent, created_at, checksum) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (memory_id, content, tags_str, agent, created_at, checksum),
        )
        self._conn.commit()

        # ChromaDB
        self._collection.add(
            ids=[memory_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[{
                "memory_id": memory_id,
                "tags": tags_str,
                "agent": agent,
                "created_at": created_at,
            }],
        )

        return memory_id

    def forget(self, memory_id: str) -> bool:
        """Delete a memory by ID.  Returns True if it existed."""
        cur = self._conn.execute(
            "DELETE FROM memories WHERE id = ?", (memory_id,)
        )
        self._conn.commit()

        try:
            self._collection.delete(ids=[memory_id])
        except Exception:
            pass

        return cur.rowcount > 0

    def forget_all(self, agent: str = "") -> int:
        """Delete all memories (optionally filtered by agent). Returns count."""
        if agent:
            cur = self._conn.execute(
                "DELETE FROM memories WHERE agent = ?", (agent,)
            )
        else:
            cur = self._conn.execute("DELETE FROM memories")
        self._conn.commit()
        deleted = cur.rowcount

        try:
            if agent:
                existing = self._collection.get(where={"agent": agent})
                if existing["ids"]:
                    self._collection.delete(ids=existing["ids"])
            else:
                # Re-create the collection to clear everything
                self._chroma.delete_collection(self._COLLECTION_NAME)
                self._collection = self._chroma.get_or_create_collection(
                    name=self._COLLECTION_NAME,
                    metadata={"description": "Agent memory store"},
                )
        except Exception:
            pass

        return deleted

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def recall(
        self,
        query: str,
        *,
        embedder,
        top_k: int = 5,
        agent: str | None = None,
        min_score: float = 0.20,
    ) -> list[dict[str, Any]]:
        """Retrieve the most relevant memories for a query.

        Parameters
        ----------
        query:
            Natural language query.
        embedder:
            An initialised ``Embedder`` instance.
        top_k:
            Maximum number of memories to return.
        agent:
            If set, only return memories from this agent.
        min_score:
            Minimum similarity score (0-1) for a memory to be included.

        Returns
        -------
        list[dict]
            Each dict: ``id``, ``content``, ``score``, ``tags``, ``agent``,
            ``created_at``.
        """
        count = self._collection.count()
        if count == 0:
            return []

        embedding = embedder.embed_texts([query])[0]
        n = min(top_k, count)

        where = {"agent": agent} if agent else None
        try:
            res = self._collection.query(
                query_embeddings=[embedding],
                n_results=n,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception:
            return []

        if not res["ids"] or not res["ids"][0]:
            return []

        results = []
        for mem_id, doc, meta, dist in zip(
            res["ids"][0],
            res["documents"][0],
            res["metadatas"][0],
            res["distances"][0],
        ):
            score = 1.0 / (1.0 + dist)
            if score < min_score:
                continue
            results.append({
                "id": mem_id,
                "content": doc,
                "score": score,
                "tags": [t for t in (meta.get("tags", "")).split(",") if t],
                "agent": meta.get("agent", ""),
                "created_at": meta.get("created_at", 0),
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results

    def list_memories(self, agent: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """List memories in reverse chronological order.

        Parameters
        ----------
        agent:
            If set, filter by agent identifier.
        limit:
            Maximum number to return.
        """
        if agent:
            cur = self._conn.execute(
                "SELECT * FROM memories WHERE agent = ? ORDER BY created_at DESC LIMIT ?",
                (agent, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )

        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "content": r["content"],
                "tags": [t for t in r["tags"].split(",") if t],
                "agent": r["agent"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def count(self) -> int:
        """Return total number of stored memories."""
        cur = self._conn.execute("SELECT COUNT(*) FROM memories")
        return cur.fetchone()[0]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()
