"""
Embex MCP Server — expose Embex as a Model Context Protocol server.

This lets AI agents (Cursor, Claude Desktop, etc.) search your codebase,
view file history, and check project status through the MCP standard.

Run with: embex serve-mcp
"""

from __future__ import annotations

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP(
    "Embex",
    description="Local-first codebase memory — semantic search and version history for AI agents.",
)


def _get_project_root() -> Path:
    """Try to find the project root from cwd."""
    from embex.config import find_project_root
    return find_project_root()


def _get_components():
    """Lazily initialize all Embex components."""
    from embex.config import load_config, chroma_path, history_db_path
    from embex.core.embedder import Embedder
    from embex.core.vector_store import VectorStore
    from embex.core.history_store import HistoryStore

    root = _get_project_root()
    config = load_config(root)
    embedder = Embedder(config)
    vector_store = VectorStore(chroma_path(root))
    history_store = HistoryStore(history_db_path(root))
    return root, config, embedder, vector_store, history_store


def _get_memory_store():
    """Lazily initialize the agent memory store."""
    from embex.config import load_config, chroma_path, memory_db_path
    from embex.core.embedder import Embedder
    from embex.core.memory_store import MemoryStore

    root = _get_project_root()
    config = load_config(root)
    embedder = Embedder(config)
    memory_store = MemoryStore(
        db_path=memory_db_path(root),
        chroma_dir=chroma_path(root),
    )
    return embedder, memory_store


# -----------------------------------------------------------------------
# MCP Tools
# -----------------------------------------------------------------------

@mcp.tool()
def search_codebase(query: str, top_k: int = 5, folder: str | None = None) -> str:
    """Search the codebase semantically using natural language.

    Args:
        query: Natural language question (e.g. "how does authentication work")
        top_k: Maximum number of results to return (default: 5)
        folder: Optional folder path to scope the search (e.g. "src/auth")

    Returns:
        Matching code chunks with file paths, similarity scores, and previews.
    """
    root, config, embedder, vector_store, history_store = _get_components()

    query_embedding = embedder.embed_query(query)
    results = vector_store.query(
        query_embedding=query_embedding,
        folder=folder,
        top_k=top_k,
    )

    history_store.close()

    if not results:
        return "No results found."

    output_parts = []
    for i, r in enumerate(results, 1):
        score = f"{r['score']:.4f}" if isinstance(r["score"], float) else str(r["score"])
        output_parts.append(
            f"--- Result {i} ---\n"
            f"File: {r['file_path']}\n"
            f"Folder: {r.get('folder', '')}\n"
            f"Language: {r.get('language', '')}\n"
            f"Score: {score}\n"
            f"Chunk #{r['chunk_index']}\n"
            f"Preview:\n{r['preview']}\n"
        )
    return "\n".join(output_parts)


@mcp.tool()
def get_file_history(file_path: str) -> str:
    """Get the version history of a specific file.

    Args:
        file_path: Relative path to the file (e.g. "src/auth/login.py")

    Returns:
        List of all versions with timestamps and checksums.
    """
    from embex.config import load_config, history_db_path
    from embex.core.history_store import HistoryStore
    from datetime import datetime, timezone

    root = _get_project_root()
    history_store = HistoryStore(history_db_path(root))

    norm_path = file_path.replace("\\", "/")
    entries = history_store.get_file_history(norm_path)
    history_store.close()

    if not entries:
        return f"No history found for '{norm_path}'."

    output_parts = [f"Version history for {norm_path}:\n"]
    for e in entries:
        ts = datetime.fromtimestamp(e["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        msg = e.get("message") or ""
        output_parts.append(f"  v{e['version']}  {ts}  checksum:{e['checksum'][:10]}  {msg}")

    return "\n".join(output_parts)


@mcp.tool()
def get_file_version(file_path: str, version: int) -> str:
    """Get the content of a specific version of a file.

    Args:
        file_path: Relative path to the file (e.g. "src/auth/login.py")
        version: Version number to retrieve

    Returns:
        The full file content at that version.
    """
    from embex.config import history_db_path
    from embex.core.history_store import HistoryStore

    root = _get_project_root()
    history_store = HistoryStore(history_db_path(root))

    norm_path = file_path.replace("\\", "/")
    content = history_store.get_snapshot(norm_path, version)
    history_store.close()

    if content is None:
        return f"Version {version} not found for '{norm_path}'."

    return f"--- {norm_path} (v{version}) ---\n{content}"


@mcp.tool()
def project_status() -> str:
    """Get an overview of the Embex project — tracked files, chunks, and versions.

    Returns:
        Summary of all collections, tracked files, and version counts.
    """
    from embex.config import load_config, chroma_path, history_db_path
    from embex.core.vector_store import VectorStore
    from embex.core.history_store import HistoryStore

    root = _get_project_root()
    config = load_config(root)

    # Vector store info
    vector_store = VectorStore(chroma_path(root))
    collections = vector_store._client.list_collections()

    total_chunks = 0
    col_lines = []
    for col in collections:
        count = col.count()
        total_chunks += count
        folder = col.metadata.get("folder", "?") if col.metadata else "?"
        col_lines.append(f"  {col.name} ({folder}): {count} chunks")

    # History store info
    history_store = HistoryStore(history_db_path(root))
    cur = history_store._conn.execute(
        "SELECT file_path, current_version, language FROM file_registry ORDER BY file_path"
    )
    files = [dict(r) for r in cur.fetchall()]
    history_store.close()

    file_lines = []
    for f in files:
        file_lines.append(f"  {f['file_path']} ({f.get('language', '?')}): v{f['current_version']}")

    return (
        f"Embex Project: {root}\n"
        f"Provider: {config.embedding.provider} | Model: {config.embedding.model}\n\n"
        f"Vector Store — {total_chunks} total chunks:\n"
        + "\n".join(col_lines) + "\n\n"
        f"History Store — {len(files)} tracked files:\n"
        + "\n".join(file_lines)
    )


@mcp.tool()
def ask_codebase(question: str, top_k: int = 8, folder: str | None = None) -> str:
    """Ask a natural-language question about the codebase and get an LLM-generated answer.

    This uses Corrective RAG (CRAG): retrieves the most relevant code chunks,
    filters them for relevance, then calls the configured LLM to produce a
    grounded answer with citations back to source files.

    Args:
        question: Natural language question (e.g. "how does JWT auth work?")
        top_k: Number of code chunks to retrieve as context (default: 8)
        folder: Optional folder path to scope the search (e.g. "src/auth")

    Returns:
        LLM-generated answer grounded in the retrieved code, with file citations
        and a list of source chunks used.
    """
    from embex.core.rag import ask as rag_ask

    root, config, embedder, vector_store, history_store = _get_components()
    history_store.close()

    try:
        result = rag_ask(
            question,
            config=config,
            embedder=embedder,
            vector_store=vector_store,
            top_k=top_k,
            folder=folder,
        )
    except (EnvironmentError, RuntimeError) as exc:
        return f"Error: {exc}"

    sources_block = "\n".join(
        f"  [{i+1}] {s['file_path']} chunk#{s['chunk_index']} score={s['score']:.3f}"
        for i, s in enumerate(result["sources"])
    )

    return (
        f"**Answer:**\n{result['answer']}\n\n"
        f"**Sources ({result['relevant_count']}/{result['total_retrieved']} relevant):**\n"
        f"{sources_block}"
    )


@mcp.tool()
def remember(content: str, tags: str = "", agent: str = "") -> str:
    """Store a memory so it can be retrieved later via semantic search.

    Memories are stored in a dedicated vector store, isolated from code chunks.
    Use this to persist decisions, facts, or notes about the project.

    Args:
        content: The fact, decision, or note to remember.
        tags: Comma-separated tags for filtering (e.g. "auth,security").
        agent: Optional agent identifier to namespace the memory (e.g. "cursor").

    Returns:
        Confirmation message with the memory ID.
    """
    embedder, memory_store = _get_memory_store()
    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    try:
        memory_id = memory_store.remember(
            content,
            embedder=embedder,
            tags=tag_list,
            agent=agent,
        )
        return f"Memory stored. ID: {memory_id}"
    finally:
        memory_store.close()


@mcp.tool()
def recall(query: str, top_k: int = 5, agent: str | None = None) -> str:
    """Recall the most relevant memories for a query using semantic search.

    Args:
        query: Natural language query to search memories.
        top_k: Maximum number of memories to return (default: 5).
        agent: Optional agent identifier to filter by.

    Returns:
        Ranked list of matching memories with scores and metadata.
    """
    from datetime import datetime, timezone

    embedder, memory_store = _get_memory_store()

    try:
        results = memory_store.recall(
            query,
            embedder=embedder,
            top_k=top_k,
            agent=agent or None,
        )
    finally:
        memory_store.close()

    if not results:
        return "No relevant memories found."

    parts = []
    for i, r in enumerate(results, 1):
        ts = datetime.fromtimestamp(r["created_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        tags_str = f"  tags: {', '.join(r['tags'])}" if r["tags"] else ""
        parts.append(
            f"[{i}] score={r['score']:.3f}  {ts}{tags_str}\n"
            f"    {r['content']}\n"
            f"    id: {r['id']}"
        )
    return "\n\n".join(parts)


@mcp.tool()
def list_memories(agent: str | None = None, limit: int = 20) -> str:
    """List all stored agent memories in reverse chronological order.

    Args:
        agent: Optional agent identifier to filter by.
        limit: Maximum number of memories to list (default: 20).

    Returns:
        Formatted list of memories with IDs, timestamps, and content.
    """
    from datetime import datetime, timezone

    embedder, memory_store = _get_memory_store()

    try:
        memories = memory_store.list_memories(agent=agent, limit=limit)
        total = memory_store.count()
    finally:
        memory_store.close()

    if not memories:
        return "No memories stored yet."

    parts = [f"Agent Memories ({total} total):"]
    for m in memories:
        ts = datetime.fromtimestamp(m["created_at"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        tags_str = f"  [{', '.join(m['tags'])}]" if m["tags"] else ""
        agent_str = f"  agent={m['agent']}" if m["agent"] else ""
        parts.append(f"  {m['id'][:8]}...  {ts}{tags_str}{agent_str}\n    {m['content'][:200]}")

    return "\n\n".join(parts)


# -----------------------------------------------------------------------
# MCP Resources
# -----------------------------------------------------------------------

@mcp.resource("embex://config")
def get_config() -> str:
    """Return the current embex.json configuration."""
    import json
    from embex.config import load_config

    root = _get_project_root()
    config = load_config(root)
    return json.dumps(config.model_dump(), indent=2)


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

def run_mcp_server() -> None:
    """Start the MCP server using stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_mcp_server()
