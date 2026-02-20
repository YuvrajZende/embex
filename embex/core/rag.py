"""
Corrective RAG (CRAG) pipeline for Embex.

Flow:
  1. Retrieve top-k code chunks via semantic search.
  2. Score each chunk for relevance to the query (cosine similarity threshold).
  3. If enough relevant chunks found  → use them as context.
     If too few                       → fall back to the full retrieved set.
  4. Call the z.ai LLM (GLM models) with the chunks as grounding context
     and return a natural-language answer.

The LLM is given a strict system prompt that tells it to:
  - Cite the file path for every claim.
  - Say "I don't know" if the code doesn't contain the answer.
  - Never hallucinate code that isn't in the retrieved chunks.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from embex.config import EmbexConfig

# Minimum similarity score (0-1) for a chunk to be considered "relevant".
_RELEVANCE_THRESHOLD = 0.30

# How much of each chunk to include in the context window (chars).
_MAX_CHUNK_CHARS = 1_200


# ---------------------------------------------------------------------------
# Main public entry point
# ---------------------------------------------------------------------------

def ask(
    question: str,
    *,
    config: "EmbexConfig",
    embedder,
    vector_store,
    top_k: int = 8,
    folder: str | None = None,
    relevance_threshold: float | None = None,
) -> dict[str, Any]:
    """Run the full CRAG pipeline and return a structured result.

    Parameters
    ----------
    question:
        The natural-language question from the user or agent.
    config:
        The loaded EmbexConfig.
    embedder:
        An initialised ``Embedder`` instance.
    vector_store:
        An initialised ``VectorStore`` instance.
    top_k:
        How many chunks to retrieve initially.
    folder:
        Optional folder scope for retrieval.
    relevance_threshold:
        Override the default similarity threshold.

    Returns
    -------
    dict with keys:
        - ``answer``  (str)  — LLM-generated answer grounded in the code.
        - ``sources`` (list) — list of dicts: file_path, score, preview.
        - ``relevant_count`` (int) — number of chunks above the threshold.
        - ``total_retrieved`` (int) — total retrieved before filtering.
    """
    threshold = relevance_threshold if relevance_threshold is not None else _RELEVANCE_THRESHOLD

    # ── Step 1: Retrieve ────────────────────────────────────────────────
    query_embedding = embedder.embed_query(question)
    results = vector_store.query(
        query_embedding=query_embedding,
        folder=folder,
        top_k=top_k,
    )

    # ── Step 2: Corrective filter ───────────────────────────────────────
    relevant = [r for r in results if r["score"] >= threshold]
    # If nothing cleared the threshold, fall back to the entire retrieved set
    context_chunks = relevant if relevant else results

    # ── Step 3: Build context string ────────────────────────────────────
    context_parts: list[str] = []
    sources: list[dict] = []
    for r in context_chunks:
        preview = r.get("preview", "")[:_MAX_CHUNK_CHARS]
        context_parts.append(
            f"### {r['file_path']} (chunk #{r['chunk_index']}, score={r['score']:.3f})\n"
            f"```\n{preview}\n```"
        )
        sources.append({
            "file_path": r["file_path"],
            "chunk_index": r["chunk_index"],
            "score": r["score"],
            "preview": preview,
            "language": r.get("language", ""),
            "folder": r.get("folder", ""),
        })

    context_str = "\n\n".join(context_parts) if context_parts else "(No code chunks retrieved.)"

    # ── Step 4: Call LLM ────────────────────────────────────────────────
    answer = _call_llm(
        question=question,
        context=context_str,
        config=config,
    )

    return {
        "answer": answer,
        "sources": sources,
        "relevant_count": len(relevant),
        "total_retrieved": len(results),
    }


# ---------------------------------------------------------------------------
# LLM call helpers
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are Embex, an expert code assistant with deep knowledge of the project's codebase.
You are given retrieved code chunks from the project as grounding context.

Rules:
1. Answer the user's question using ONLY the provided code chunks.
2. For every claim, cite the exact file path (e.g. "In `src/auth/login.py`...").
3. If the retrieved chunks do not contain enough information to answer, say exactly:
   "I don't have enough code context to answer that confidently. Try running `embex init` to re-index or widen the search with --folder."
4. Do NOT hallucinate code, function names, or file paths not present in the chunks.
5. Format code with proper markdown code blocks and language tags.
6. Be concise but complete — prefer bullet points for multi-part answers.
"""


def _call_llm(question: str, context: str, config: "EmbexConfig") -> str:
    """Call the z.ai LLM with the question and retrieved context."""
    return _call_zai(question, context, config)


def _build_messages(question: str, context: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Here are the relevant code chunks from the project:\n\n"
                f"{context}\n\n"
                f"---\n\n"
                f"Question: {question}"
            ),
        },
    ]


def _call_zai(question: str, context: str, config: "EmbexConfig") -> str:
    """Call the z.ai API (GLM models, OpenAI-compatible)."""
    try:
        from dotenv import load_dotenv
        from pathlib import Path as _Path
        load_dotenv()  # project-local .env
        load_dotenv(dotenv_path=_Path.home() / ".embex" / ".env", override=False)  # global fallback
    except ImportError:
        pass

    from openai import OpenAI

    api_key = os.environ.get(config.llm.api_key_env)
    if not api_key:
        raise EnvironmentError(
            f"Z.ai API key not set. Set the '{config.llm.api_key_env}' environment variable."
        )

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.z.ai/api/paas/v4/",
    )
    response = client.chat.completions.create(
        model=config.llm.model or "glm-4.7-flash",
        messages=_build_messages(question, context),
        extra_body={"thinking": {"type": "disabled"}},
        temperature=0.7,
        max_tokens=2048,
    )
    msg = response.choices[0].message
    return msg.content or getattr(msg, "reasoning_content", None) or ""
