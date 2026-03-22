"""
RAG (Retrieval-Augmented Generation) pipeline for Embex.

How it works:
  1. Search for relevant code chunks using embeddings
  2. Filter chunks by similarity score
  3. Send the relevant chunks to the LLM as context
  4. Return the LLM's answer with source citations
"""

import os


# Default settings
RELEVANCE_THRESHOLD = 0.30  # minimum similarity score to count as relevant
MAX_CHUNK_CHARS = 1200      # max characters per chunk to send to LLM


def ask(question, config, embedder, vector_store, top_k=8, folder=None, relevance_threshold=None):
    """Run the RAG pipeline: retrieve chunks, filter, generate answer.
    
    Returns a dict with: answer, sources, relevant_count, total_retrieved.
    """
    threshold = relevance_threshold if relevance_threshold is not None else RELEVANCE_THRESHOLD

    # Step 1: Search for relevant code chunks
    query_embedding = embedder.embed_query(question)
    results = vector_store.query(
        query_embedding=query_embedding,
        folder=folder,
        top_k=top_k,
    )

    # Step 2: Filter by relevance score
    relevant = [r for r in results if r["score"] >= threshold]
    # If nothing is relevant enough, use all results as fallback
    context_chunks = relevant if relevant else results

    # Step 3: Build the context string for the LLM
    context_parts = []
    sources = []
    for r in context_chunks:
        preview = r.get("preview", "")[:MAX_CHUNK_CHARS]
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

    # Step 4: Call the LLM to generate an answer
    answer = _call_llm(question, context_str, config)

    return {
        "answer": answer,
        "sources": sources,
        "relevant_count": len(relevant),
        "total_retrieved": len(results),
    }


# System prompt that tells the LLM how to behave
SYSTEM_PROMPT = """\
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


def _call_llm(question, context, config):
    """Call the z.ai LLM API to generate an answer."""
    # Load environment variables
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        load_dotenv()
        load_dotenv(dotenv_path=Path.home() / ".embex" / ".env", override=False)
    except ImportError:
        pass

    from openai import OpenAI

    api_key = os.environ.get(config.llm.api_key_env)
    if not api_key:
        raise EnvironmentError(
            f"API key not set. Set the '{config.llm.api_key_env}' environment variable."
        )

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.z.ai/api/paas/v4/",
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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

    response = client.chat.completions.create(
        model=config.llm.model or "glm-4.7-flash",
        messages=messages,
        extra_body={"thinking": {"type": "disabled"}},
        temperature=0.7,
        max_tokens=2048,
    )

    msg = response.choices[0].message
    return msg.content or getattr(msg, "reasoning_content", None) or ""
