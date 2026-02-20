"""
Embex Python SDK — public API for AI agents and integrations.

Usage::

    from embex.sdk import Embex

    ex = Embex("/path/to/project")

    # Semantic chunk search
    results = ex.search("how does auth work", top_k=5)

    # CRAG — get an LLM-generated answer grounded in the codebase
    answer = ex.ask("how does JWT auth work?")
    print(answer["answer"])
    for src in answer["sources"]:
        print(src["file_path"], src["score"])

    # Agent memory
    ex.remember("We use HS256 JWT tokens for API auth", tags=["auth"])
    memories = ex.recall("authentication tokens")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from embex.config import load_config, chroma_path, memory_db_path, find_project_root
from embex.core.embedder import Embedder
from embex.core.vector_store import VectorStore


class Embex:
    """High-level interface for querying an Embex-indexed project."""

    def __init__(self, project_path: Optional[str | Path] = None) -> None:
        """Initialize the SDK.

        Parameters
        ----------
        project_path:
            Path to the project root (must contain ``.embex/``).
            If ``None``, walks up from cwd to find it.
        """
        if project_path:
            self._root = Path(project_path).resolve()
        else:
            self._root = find_project_root()

        self._config = load_config(self._root)
        self._embedder = Embedder(self._config)
        self._store = VectorStore(chroma_path(self._root))

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        folder: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search across the embedded codebase.

        Parameters
        ----------
        query:
            Natural language question.
        folder:
            Optional folder path to scope the search.
        top_k:
            Maximum number of results.

        Returns
        -------
        list[dict]
            Each dict has: ``file_path``, ``chunk_index``, ``score``,
            ``preview``, ``folder``, ``language``.
        """
        embedding = self._embedder.embed_query(query)
        return self._store.query(
            query_embedding=embedding,
            folder=folder,
            top_k=top_k,
        )

    # ------------------------------------------------------------------
    # CRAG — ask a question and get an LLM-grounded answer
    # ------------------------------------------------------------------

    def ask(
        self,
        question: str,
        folder: Optional[str] = None,
        top_k: int = 8,
        relevance_threshold: float = 0.30,
    ) -> dict[str, Any]:
        """Ask a natural-language question and get an LLM-generated answer grounded in the codebase.

        Uses Corrective RAG: retrieve → filter for relevance → generate answer.

        Parameters
        ----------
        question:
            Natural language question (e.g. "how does JWT auth work?").
        folder:
            Optional folder path to scope the retrieval.
        top_k:
            Number of chunks to retrieve initially.
        relevance_threshold:
            Minimum similarity score (0-1) for a chunk to count as relevant.

        Returns
        -------
        dict with keys:
            - ``answer`` (str) — LLM-generated grounded answer.
            - ``sources`` (list) — chunks used as context.
            - ``relevant_count`` (int) — chunks above threshold.
            - ``total_retrieved`` (int) — total before filtering.
        """
        from embex.core.rag import ask as rag_ask

        return rag_ask(
            question,
            config=self._config,
            embedder=self._embedder,
            vector_store=self._store,
            top_k=top_k,
            folder=folder,
            relevance_threshold=relevance_threshold,
        )

    # ------------------------------------------------------------------
    # Agent memory layer
    # ------------------------------------------------------------------

    @property
    def _memory_store(self):
        """Lazily initialised MemoryStore (created on first access)."""
        if not hasattr(self, "_memory_store_instance"):
            from embex.core.memory_store import MemoryStore
            self._memory_store_instance = MemoryStore(
                db_path=memory_db_path(self._root),
                chroma_dir=chroma_path(self._root),
            )
        return self._memory_store_instance

    def remember(
        self,
        content: str,
        tags: Optional[list[str]] = None,
        agent: str = "",
    ) -> str:
        """Persist a memory (fact, decision, note) for future semantic recall.

        Parameters
        ----------
        content:
            The text to remember.
        tags:
            Optional list of tag strings for filtering.
        agent:
            Optional agent identifier to namespace the memory.

        Returns
        -------
        str
            The unique memory ID.
        """
        return self._memory_store.remember(
            content,
            embedder=self._embedder,
            tags=tags,
            agent=agent,
        )

    def recall(
        self,
        query: str,
        top_k: int = 5,
        agent: Optional[str] = None,
        min_score: float = 0.20,
    ) -> list[dict[str, Any]]:
        """Retrieve the most relevant memories for a query.

        Parameters
        ----------
        query:
            Natural language query.
        top_k:
            Maximum number of memories to return.
        agent:
            If set, only return memories from this agent.
        min_score:
            Minimum similarity score (0-1).

        Returns
        -------
        list[dict]
            Each dict: ``id``, ``content``, ``score``, ``tags``, ``agent``,
            ``created_at``.
        """
        return self._memory_store.recall(
            query,
            embedder=self._embedder,
            top_k=top_k,
            agent=agent,
            min_score=min_score,
        )

    def list_memories(self, agent: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        """List all stored memories in reverse chronological order."""
        return self._memory_store.list_memories(agent=agent, limit=limit)

    def forget(self, memory_id: str) -> bool:
        """Delete a memory by ID. Returns True if it existed."""
        return self._memory_store.forget(memory_id)
