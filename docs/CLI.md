# CLI Reference

Complete reference for all `embex` commands.

---

## `embex init`

Initializes Embex in a project directory. Creates `.embex/`, scans every code file, embeds them (skipping unchanged files on re-runs via checksum cache), and stores everything locally.

```bash
embex init                          # initialize current directory
embex init C:\Projects\my-app       # initialize a specific path
```

Re-running `embex init` on an already-initialized project will prompt you before re-scanning. Only files whose content has changed since the last embed will be re-processed.

---

## `embex watch`

Watches the project directory for file changes. On every save:
1. Snapshots the new version in the history database
2. Re-embeds the file so search results stay fresh

```bash
embex watch
```

Leave this running in a terminal while you code. Press `Ctrl+C` to stop.

---

## `embex query`

Semantic search — finds the most relevant code chunks for a natural-language query.

```bash
embex query "how does user authentication work"
embex query "database connection" --top-k 10
embex query "error handling" --folder src/utils
```

| Flag | Default | Description |
|---|---|---|
| `--top-k` | 5 | Number of chunks to return |
| `--folder` | — | Scope search to a subfolder |

**Output:**
```
┌─────────────────── Search Results ───────────────────┐
│ #  │ File                  │ Chunk │ Score  │ Preview │
│ 1  │ src/auth/login.py     │   0   │ 0.823  │ def ... │
│ 2  │ src/auth/signup.py    │   0   │ 0.789  │ def ... │
└──────────────────────────────────────────────────────┘
```

---

## `embex ask`

CRAG pipeline — retrieves relevant code chunks, filters by similarity, and sends them to an LLM to generate a grounded, cited answer.

```bash
embex ask "how does authentication work"
embex ask "where are database queries made" --folder src/db
embex ask "explain the chunking strategy"   --top-k 10
embex ask "how is error handling done"      --threshold 0.4
```

| Flag | Default | Description |
|---|---|---|
| `--top-k` | 8 | Chunks to retrieve |
| `--folder` | — | Scope to a subfolder |
| `--threshold` | 0.30 | Min similarity score (0–1) to count as relevant |
| `--no-sources` | — | Hide the source panel |

**Output:**
```
─────────────────────── Answer ────────────────────────
In `src/auth/login.py`, the `login()` function validates
credentials using `check_password()`...

─────────────────────── Sources ───────────────────────
5/8 chunks above 30% threshold

  ● src/auth/login.py   chunk #0  score=0.872
    def login(username, password): ...
```

---

## `embex explain`

Analyzes a file — static analysis by default, LLM summary with `--llm`.

```bash
embex explain src/auth/login.py           # static (free, instant)
embex explain src/auth/login.py --llm     # LLM-powered summary
embex explain src/auth/login.py --llm --model glm-4.7
```

Static output covers: total lines, imports, classes, functions, docstrings, and semantically related files.

---

## `embex memory`

Persistent, semantically searchable memory for AI agents. Stored in `.embex/memory.db`, isolated from code chunks.

```bash
# Store a decision
embex memory add "We use HS256 JWT tokens for API auth"
embex memory add "Payment service uses Stripe webhooks" --tags payments,stripe --agent cursor

# Retrieve by meaning
embex memory recall "authentication approach"
embex memory recall "payment processing" --top-k 3 --agent cursor

# List / manage
embex memory list
embex memory list --agent cursor --limit 10
embex memory forget a1b2c3d4      # delete by ID prefix
embex memory clear --yes           # wipe all
```

---

## `embex log`

Shows the full version history of a file.

```bash
embex log src/auth/login.py
```

```
┌──────────────── Version History ─────────────────┐
│ Version │ Timestamp            │ Checksum         │
│    3    │ 2026-02-17 16:36:03  │ bc5c05114d       │
│    2    │ 2026-02-17 16:33:21  │ 6a0cd15930       │
│    1    │ 2026-02-17 16:24:03  │ 8e56d4f238       │
└──────────────────────────────────────────────────┘
```

---

## `embex diff`

Side-by-side diff between two versions of a file.

```bash
embex diff src/auth/login.py              # last two versions
embex diff src/auth/login.py --v1 1 --v2 3
```

```
╭──── src/auth/login.py  v1 → v3 ────╮
│ -print("hello world")              │
│ +print("hello mate")               │
╰─────────────────────────────────────╯
```

---

## `embex restore`

Restores a file on disk to any previous version — the core "undo" feature.

```bash
embex restore src/auth/login.py --version 1
```

Embex asks for confirmation before overwriting. After restore, the watcher won't create a redundant snapshot (checksum match).

---

## `embex status`

Shows what's inside the Embex database.

```bash
embex status
```

```
Embex Project: C:\Projects\my-app
Provider: local  |  Model: all-MiniLM-L6-v2

┌───────── Vector Store ─────────┐    ┌────────── History ─────────────┐
│ Folder     │ Chunks            │    │ File              │ Versions    │
│ src/auth   │ 4                 │    │ src/auth/login.py │ 3           │
│ root       │ 2                 │    │ src/auth/signup.py│ 1           │
│ Total      │ 6                 │    │ 2 files           │ 4 total     │
└────────────────────────────────┘    └─────────────────────────────────┘
```

---

## `embex search`

Exact text or regex search (different from `query` which is semantic).

```bash
embex search "def login"
embex search "TODO:.*" --regex
embex search "api_key" --folder src/config
```

---

## `embex stats`

Project-wide statistics: file count, database size, most-changed files.

```bash
embex stats
```

---

## `embex similar`

Finds files semantically similar to a given file — useful for spotting duplicate logic.

```bash
embex similar src/auth/login_v2.py
```

---

## `embex ignore`

Adds patterns to the exclusion list in `embex.json`.

```bash
embex ignore "*.log"
embex ignore "temp_data" --dir
```

---

## `embex serve-mcp`

Starts the MCP server for AI agent integration. See [MCP.md](./MCP.md) for full details.

```bash
embex serve-mcp
```
