"""
Configuration module for Embex.
Handles loading, saving, and validating the embex.json config file.
"""

import json
import time
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


# --- Config Models ---

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
    chunk_size: int = 200
    overlap: int = 20


class HistoryConfig(BaseModel):
    enabled: bool = True
    max_versions_per_file: int = 50


class LLMConfig(BaseModel):
    provider: str = "zai"
    model: str = "glm-4.7-flash"
    api_key_env: str = "ZAI_API_KEY"


class EmbexConfig(BaseModel):
    version: str = "1.0"
    project_name: str = "my-project"
    created_at: int = Field(default_factory=lambda: int(time.time()))
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    watch: WatchConfig = Field(default_factory=WatchConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)


# --- Constants ---

EMBEX_DIR = ".embex"
CONFIG_FILE = "embex.json"
CHROMA_DIR = "chroma"
HISTORY_DB = "history.db"


# --- Helper Functions ---

def embex_dir(project_root: Path) -> Path:
    """Get the .embex directory path."""
    return project_root / EMBEX_DIR


def config_path(project_root: Path) -> Path:
    """Get the embex.json file path."""
    return embex_dir(project_root) / CONFIG_FILE


def chroma_path(project_root: Path) -> Path:
    """Get the ChromaDB storage directory path."""
    return embex_dir(project_root) / CHROMA_DIR


def history_db_path(project_root: Path) -> Path:
    """Get the SQLite history database path."""
    return embex_dir(project_root) / HISTORY_DB


def create_default_config(project_name: str) -> EmbexConfig:
    """Create a new config with default settings."""
    return EmbexConfig(project_name=project_name)


def write_config(project_root: Path, config: EmbexConfig) -> None:
    """Save the config to .embex/embex.json."""
    path = config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config.model_dump(), indent=2) + "\n",
        encoding="utf-8",
    )


def load_config(project_root: Path) -> EmbexConfig:
    """Load config from .embex/embex.json."""
    path = config_path(project_root)
    if not path.exists():
        raise FileNotFoundError(f"No embex.json found at {path}. Run 'embex init' first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return EmbexConfig(**data)


def find_project_root(start: Optional[Path] = None) -> Path:
    """Walk up from start directory to find the .embex/ project root."""
    current = (start or Path.cwd()).resolve()
    while True:
        if (current / EMBEX_DIR / CONFIG_FILE).exists():
            return current
        parent = current.parent
        if parent == current:
            raise FileNotFoundError("No .embex/ directory found. Run 'embex init' first.")
        current = parent
