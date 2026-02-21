# Embex

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python) ![License](https://img.shields.io/badge/License-MIT-green) ![Status](https://img.shields.io/badge/Status-Active-brightgreen)

**Local-first memory layer for AI agents — semantic search, CRAG Q&A, and persistent memory over your codebase. Zero cloud. Zero cost.**

---

## What it does

- **Embeds your codebase** into a local ChromaDB vector database in one command
- **Answers natural-language questions** about code using CRAG (retrieve → filter → LLM answer with file citations)
- **Snapshots every change** automatically, so you can restore deleted or modified files
- **Stores agent memories** semantically, surviving across sessions
- **Exposes everything as an MCP server** — plug Cursor, Claude Desktop, or Cline directly into your codebase

---

## Install

```bash
git clone https://github.com/your-username/embex.git
cd embex && pip install -e .
```

No Docker. No cloud accounts. No API keys for core functionality.

---

## Quick Start

```bash
cd /path/to/your-project

embex init                                  # embed entire codebase (skips unchanged files)
embex watch                                 # watch for changes in background

embex query "authentication flow"           # semantic chunk search
embex ask   "how does JWT refresh work"     # grounded LLM answer with citations
embex explain src/auth/token.py             # explain a specific file
```

---

## Python SDK

Give any AI agent full codebase awareness in 10 lines:

```python
from embex import EmbexSDK

sdk = EmbexSDK("/path/to/your-project")

# Semantic search
results = sdk.search("authentication logic", top_k=5)
for r in results:
    print(r["file"], r["score"])

# Q&A with citations
answer = sdk.ask("How does JWT refresh work?")
print(answer["answer"])
print(answer["sources"])

# Agent memory — persists across sessions
sdk.remember("User prefers async/await over callbacks", tags=["code-style"])
memories = sdk.recall("coding style preferences")

# File history
history = sdk.get_file_history("src/auth/token.py")
old_version = sdk.get_file_version("src/auth/token.py", version_id=history[0]["id"])
```

---

## MCP Server — AI Agent Integration

Connect Cursor, Claude Desktop, or any MCP client to your codebase:

```bash
embex serve-mcp   # run from your project directory
```

**Claude Desktop** (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "embex": {
      "command": "embex",
      "args": ["serve-mcp"],
      "cwd": "C:/Users/you/Projects/my-app"
    }
  }
}
```

**Cursor** (`.cursor/mcp.json` in your project):

```json
{
  "mcpServers": {
    "embex": { "command": "embex", "args": ["serve-mcp"], "cwd": "." }
  }
}
```

Available MCP tools: `search_codebase`, `ask_codebase`, `remember`, `recall`, `list_memories`, `get_file_history`, `get_file_version`, `project_status`

→ Full MCP docs: [docs/MCP.md](docs/MCP.md)

---

## How it Works

```
Your codebase
      │
      ▼
 embex init / watch
      │
  ┌───┴──────────────────────────────────────┐
  │             Scanner + Chunker            │
  │  SHA-256 checksum → skip unchanged files │
  └───┬──────────────────────────────────────┘
      │
  ┌───▼──────────────────────────────────────┐
  │         Embedder (sentence-transformers) │
  │            all-MiniLM-L6-v2             │
  └───┬──────────────────────────────────────┘
      │
  ┌───▼──────────────────────────────────────┐
  │     ChromaDB  │  SQLite History Store    │
  │   (vectors)   │  (versions + checksums)  │
  └───┬──────────────────────────────────────┘
      │
  ┌───▼──────────────────────────────────────┐
  │             Query / Ask / MCP            │
  │   retrieve → filter → LLM (z.ai GLM)    │
  └──────────────────────────────────────────┘
```

---

## LLM Setup (for `ask`, `explain --llm`, MCP `ask_codebase`)

Create a global env file that applies to all projects — no per-project setup needed:

```dotenv
# ~/.embex/.env
ZAI_API_KEY=your_key_here
```

Default model: `glm-4.7-flash` (free tier). Available models: `glm-5`, `glm-4.7`, `glm-4.7-flash`, `glm-4.7-flashx`

---

## Supported Languages

Python, JavaScript, TypeScript, Java, C, C++, Go, Rust, Ruby, PHP, Swift, Kotlin, Shell, Markdown, YAML, JSON, TOML, HTML, CSS — and more.

---

## Requirements

- Python 3.10+
- No API keys for embeddings or search (runs fully offline)
- z.ai API key only needed for LLM features (`ask`, `explain --llm`)

---

## Docs

| Reference | Contents |
|---|---|
| [CLI Reference](docs/CLI.md) | All commands, flags, and output examples |
| [Configuration](docs/CONFIGURATION.md) | `embex.json` schema, z.ai models, all options |
| [MCP Integration](docs/MCP.md) | Tool listing, client setup, agent examples |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                            CLI / SDK / MCP                           │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
┌────────────────────────────────▼─────────────────────────────────────┐
│  Scanner ──► Smart Chunker (AST) ──► Embedder ──► VectorStore        │
│                    │                                                 │
│                    └──────────────────────► HistoryStore             │
│                                                                      │
│  CRAG Pipeline: VectorStore → filter → LLM → cited answer           │
│  MemoryStore: semantic memory isolated from code vectors             │
└──────────────────────────────────────────────────────────────────────┘
        │                  │                  │               │
 ┌──────▼──────┐   ┌───────▼──────┐   ┌──────▼──────┐  ┌────▼───────┐
 │  ChromaDB   │   │  SQLite      │   │  SQLite     │  │ MCP Server │
 │  (vectors)  │   │  (history)   │   │  (memory)   │  │            │
 └─────────────┘   └──────────────┘   └─────────────┘  └────────────┘
```

---

## License

MIT © 2025
