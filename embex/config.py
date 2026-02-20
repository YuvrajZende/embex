"""
Embex configuration — load, write, and validate embex.json.

Uses Pydantic models for schema validation and sensible defaults.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic config models
# ---------------------------------------------------------------------------

class EmbeddingConfig(BaseModel):
    provider: str = "local"
    model: str = "all-MiniLM-L6-v2"
    api_key_env: str = "ZAI_API_KEY"


class WatchConfig(BaseModel):
    include_extensions: list[str] = Field(default_factory=lambda: [
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".go", ".rs", ".java", ".cpp", ".c",
        ".rb", ".php", ".swift", ".kt",
    ])
    exclude_dirs: list[str] = Field(default_factory=lambda: [
        "node_modules", "__pycache__", ".git",
        ".embex", "dist", "build", ".venv", "venv",
    ])
    exclude_files: list[str] = Field(default_factory=lambda: [
        "*.test.*", "*.spec.*", "*.min.js",
    ])


class ChunkingConfig(BaseModel):
    strategy: str = "ast"
    chunk_size: int = 200
    overlap: int = 20


class HistoryConfig(BaseModel):
    enabled: bool = True
    max_versions_per_file: int = 50


class LLMConfig(BaseModel):
    provider: str = "zai"  # z.ai (GLM models)
    model: str = "glm-4.7-flash"
    api_key_env: str = "ZAI_API_KEY"


class RAGConfig(BaseModel):
    top_k: int = 8                       # initial chunks to retrieve
    relevance_threshold: float = 0.30    # min similarity score to be "relevant"
    max_chunk_chars: int = 1200          # chars per chunk sent to LLM


class EmbexConfig(BaseModel):
    version: str = "1.0"
    project_name: str = "my-project"
    created_at: int = Field(default_factory=lambda: int(time.time()))
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    watch: WatchConfig = Field(default_factory=WatchConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEX_DIR = ".embex"
CONFIG_FILE = "embex.json"
CHROMA_DIR = "chroma"
HISTORY_DB = "history.db"
MEMORY_DB = "memory.db"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def embex_dir(project_root: Path) -> Path:
    """Return the .embex directory for a project root."""
    return project_root / EMBEX_DIR


def config_path(project_root: Path) -> Path:
    """Return the path to embex.json."""
    return embex_dir(project_root) / CONFIG_FILE


def chroma_path(project_root: Path) -> Path:
    """Return the path to the ChromaDB storage directory."""
    return embex_dir(project_root) / CHROMA_DIR


def history_db_path(project_root: Path) -> Path:
    """Return the path to the SQLite history database."""
    return embex_dir(project_root) / HISTORY_DB


def memory_db_path(project_root: Path) -> Path:
    """Return the path to the agent memory SQLite database."""
    return embex_dir(project_root) / MEMORY_DB


def create_default_config(project_name: str) -> EmbexConfig:
    """Create a new EmbexConfig with sensible defaults."""
    return EmbexConfig(project_name=project_name)


def write_config(project_root: Path, config: EmbexConfig) -> None:
    """Write the config to .embex/embex.json."""
    path = config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config.model_dump(), indent=2) + "\n",
        encoding="utf-8",
    )


def load_config(project_root: Path) -> EmbexConfig:
    """Load and validate the config from .embex/embex.json."""
    path = config_path(project_root)
    if not path.exists():
        raise FileNotFoundError(
            f"No embex.json found at {path}. Run 'embex init' first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return EmbexConfig(**data)


def find_project_root(start: Optional[Path] = None) -> Path:
    """Walk up from *start* (default: cwd) looking for .embex/ directory."""
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / EMBEX_DIR / CONFIG_FILE).exists():
            return current
        parent = current.parent
        if parent == current:
            raise FileNotFoundError(
                "No .embex/ directory found. Run 'embex init' first."
            )
        current = parent
