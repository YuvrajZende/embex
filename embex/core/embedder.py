"""
Embedder — generates vector embeddings for text using either OpenAI API or a local model.
"""

import os


# Max batch size
MAX_BATCH = 2048


class Embedder:
    """Generates embeddings using OpenAI or a local sentence-transformers model."""

    def __init__(self, config):
        self.provider = config.embedding.provider

        if self.provider == "local":
            self._setup_local(config.embedding.model)
        else:
            self._setup_openai(config)

    def _setup_openai(self, config):
        """Set up OpenAI client for embeddings."""
        # Load .env if present
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
                "Set 'embedding.provider' to 'local' in embex.json to use free offline embeddings."
            )
        self.client = OpenAI(api_key=api_key)
        self.model_name = config.embedding.model

    def _setup_local(self, model_name):
        """Set up local sentence-transformers model."""
        from sentence_transformers import SentenceTransformer

        # Use default local model if user has an OpenAI model name
        if model_name.startswith("text-embedding"):
            model_name = "all-MiniLM-L6-v2"

        self.local_model = SentenceTransformer(model_name)
        self.model_name = model_name

    def embed_texts(self, texts):
        """Generate embeddings for a list of text strings."""
        if not texts:
            return []

        if self.provider == "local":
            return self._embed_local(texts)
        return self._embed_openai(texts)

    def embed_query(self, query):
        """Embed a single query string and return its vector."""
        return self.embed_texts([query])[0]

    def _embed_openai(self, texts):
        """Generate embeddings using OpenAI API."""
        all_embeddings = []
        for i in range(0, len(texts), MAX_BATCH):
            batch = texts[i : i + MAX_BATCH]
            response = self.client.embeddings.create(
                input=batch,
                model=self.model_name,
            )
            sorted_data = sorted(response.data, key=lambda d: d.index)
            all_embeddings.extend([d.embedding for d in sorted_data])
        return all_embeddings

    def _embed_local(self, texts):
        """Generate embeddings using local sentence-transformers model."""
        embeddings = self.local_model.encode(texts, show_progress_bar=False)
        return [e.tolist() for e in embeddings]
