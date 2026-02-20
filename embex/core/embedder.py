"""
Embedder — generate embeddings using OpenAI API or local models.

Supports two providers:
- ``"openai"`` — uses OpenAI's API (requires API key + credits)
- ``"local"``  — uses sentence-transformers, runs 100% offline, free
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from embex.config import EmbexConfig

# OpenAI batch limit
_MAX_BATCH = 2048


class Embedder:
    """Generate embeddings using either OpenAI or a local model."""

    def __init__(self, config: "EmbexConfig") -> None:
        self._provider = config.embedding.provider

        if self._provider == "local":
            self._init_local(config.embedding.model)
        else:
            self._init_openai(config)

    # ------------------------------------------------------------------
    # Provider initialisation
    # ------------------------------------------------------------------

    def _init_openai(self, config: "EmbexConfig") -> None:
        # Load .env file if present
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        from openai import OpenAI

        api_key = os.environ.get(config.embedding.api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"Environment variable '{config.embedding.api_key_env}' is not set. "
                "Embex needs an OpenAI API key for generating embeddings.\n"
                "Tip: Set 'embedding.provider' to 'local' in embex.json "
                "to use free offline embeddings instead."
            )
        self._client = OpenAI(api_key=api_key)
        self._model_name = config.embedding.model

    def _init_local(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        # Default local model if the user still has the OpenAI model name
        if model_name.startswith("text-embedding"):
            model_name = "all-MiniLM-L6-v2"

        self._local_model = SentenceTransformer(model_name)
        self._model_name = model_name

    # ------------------------------------------------------------------
    # Embedding methods
    # ------------------------------------------------------------------

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of text strings.

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, same order.
        """
        if not texts:
            return []

        if self._provider == "local":
            return self._embed_local(texts)
        return self._embed_openai(texts)

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        return self.embed_texts([query])[0]

    # ------------------------------------------------------------------
    # Provider-specific implementations
    # ------------------------------------------------------------------

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), _MAX_BATCH):
            batch = texts[i : i + _MAX_BATCH]
            response = self._client.embeddings.create(
                input=batch,
                model=self._model_name,
            )
            sorted_data = sorted(response.data, key=lambda d: d.index)
            all_embeddings.extend([d.embedding for d in sorted_data])
        return all_embeddings

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._local_model.encode(texts, show_progress_bar=False)
        return [e.tolist() for e in embeddings]
