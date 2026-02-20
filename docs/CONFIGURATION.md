# Configuration Reference

Embex is configured via `.embex/embex.json` in your project root. Run `embex init` to generate it with sensible defaults.

---

## Full Schema

```json
{
  "version": "1.0",
  "project_name": "my-app",
  "embedding": {
    "provider": "local",
    "model": "all-MiniLM-L6-v2",
    "api_key_env": "ZAI_API_KEY"
  },
  "llm": {
    "provider": "zai",
    "model": "glm-4.7-flash",
    "api_key_env": "ZAI_API_KEY"
  },
  "rag": {
    "top_k": 8,
    "relevance_threshold": 0.30,
    "max_chunk_chars": 1200
  },
  "watch": {
    "include_extensions": [
      ".py", ".js", ".ts", ".jsx", ".tsx",
      ".go", ".rs", ".java", ".cpp", ".c",
      ".rb", ".php", ".swift", ".kt"
    ],
    "exclude_dirs": [
      "node_modules", "__pycache__", ".git",
      ".embex", "dist", "build", ".venv", "venv"
    ],
    "exclude_files": ["*.test.*", "*.spec.*", "*.min.js"]
  },
  "chunking": {
    "strategy": "ast",
    "chunk_size": 200,
    "overlap": 20
  },
  "history": {
    "enabled": true,
    "max_versions_per_file": 50
  }
}
```

---

## Field Reference

### `embedding`

| Field | Default | Description |
|---|---|---|
| `provider` | `"local"` | `"local"` — free, runs offline (sentence-transformers). `"openai"` — paid, requires API key. |
| `model` | `"all-MiniLM-L6-v2"` | Model name. For local: any sentence-transformers model. For openai: e.g. `"text-embedding-3-small"`. |
| `api_key_env` | `"ZAI_API_KEY"` | Name of the environment variable holding the API key (only relevant for non-local providers). |

### `llm`

Used by `embex ask` and `embex explain --llm`.

| Field | Default | Description |
|---|---|---|
| `provider` | `"zai"` | `"zai"` — z.ai GLM models. `"ollama"` — local, no API key needed. |
| `model` | `"glm-4.7-flash"` | Model name. For z.ai: `glm-5`, `glm-4.7`, `glm-4.7-flash`, `glm-4.5-flash`, etc. For ollama: e.g. `llama3`. |
| `api_key_env` | `"ZAI_API_KEY"` | Environment variable name for the LLM API key. |

**z.ai model options:**

| Model | Speed | Quality | Notes |
|---|---|---|---|
| `glm-4.7-flash` | ⚡ Fast | Good | Default — best balance |
| `glm-4.7` | Medium | Better | Full flagship |
| `glm-5` | Slower | Best | Latest, most capable |
| `glm-4.5-flash` | ⚡ Fast | Good | Older fast model |

**Ollama (fully offline):**
```json
{ "llm": { "provider": "ollama", "model": "llama3" } }
```

### `rag`

Controls the CRAG retrieval pipeline used by `embex ask`.

| Field | Default | Description |
|---|---|---|
| `top_k` | `8` | Number of code chunks retrieved initially |
| `relevance_threshold` | `0.30` | Min similarity score (0–1) for a chunk to count as "relevant" |
| `max_chunk_chars` | `1200` | Max characters per chunk sent to the LLM context window |

### `watch`

Controls which files `embex watch` and `embex init` track.

| Field | Default | Description |
|---|---|---|
| `include_extensions` | `.py .js .ts ...` | File extensions to track |
| `exclude_dirs` | `node_modules .git ...` | Directories to skip entirely |
| `exclude_files` | `*.test.* *.min.js` | Glob patterns for files to skip |

### `chunking`

| Field | Default | Description |
|---|---|---|
| `strategy` | `"ast"` | `"ast"` — splits on function/class boundaries (recommended). `"fixed"` — splits by line count. |
| `chunk_size` | `200` | Lines per chunk (only used with `"fixed"` strategy) |
| `overlap` | `20` | Overlapping lines between chunks (only used with `"fixed"` strategy) |

### `history`

| Field | Default | Description |
|---|---|---|
| `enabled` | `true` | Whether to snapshot file versions in SQLite |
| `max_versions_per_file` | `50` | Maximum snapshots stored per file |

---

## API Key Setup

Embex looks for API keys using this priority order:

1. **Project-local `.env`** — `.env` file in the project root
2. **Global fallback** — `~/.embex/.env`

Create `~/.embex/.env` once and every project will use it automatically:

```dotenv
ZAI_API_KEY=your-key-here
```

You never need to copy `.env` files between projects.
