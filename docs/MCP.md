# MCP Server — AI Agent Integration

Embex includes a built-in **Model Context Protocol (MCP) server**, making it instantly usable by AI coding tools — Cursor, Claude Desktop, Windsurf, Cline, and any other MCP-compatible client.

---

## Starting the Server

```bash
# Run from your project directory
cd C:\Projects\my-app
embex serve-mcp
```

The server reads the local `.embex/` database and exposes your codebase + memory as MCP tools.

---

## Available Tools

| Tool | Description |
|---|---|
| `search_codebase` | Semantic search — returns raw code chunks ranked by similarity |
| `ask_codebase` | CRAG Q&A — LLM-generated answer grounded in code, with file citations |
| `remember` | Store a memory for future semantic retrieval |
| `recall` | Retrieve the most relevant memories for a query |
| `list_memories` | List all stored agent memories |
| `get_file_history` | View snapshot history of a file |
| `get_file_version` | Retrieve full content of a specific file version |
| `project_status` | Overview of tracked files, chunks, and versions |

---

## Claude Desktop

Add to `claude_desktop_config.json` (usually `~/.claude/claude_desktop_config.json`):

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

Restart Claude Desktop. The agent can now search your codebase, ask questions, and manage memories across sessions.

---

## Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "embex": {
      "command": "embex",
      "args": ["serve-mcp"],
      "cwd": "."
    }
  }
}
```

---

## Windsurf / Cline / Other MCP Clients

Any client that implements the MCP stdio transport works. Use:

- **Command:** `embex serve-mcp`
- **Working directory:** path to your project (where `.embex/` lives)

---

## Example Agent Session

Once connected, agents can use natural language to call tools:

```
Agent: What files handle payment processing in this project?
→ [calls search_codebase("payment processing")]
→ Returns: src/payments/stripe.py (0.891), src/payments/webhook.py (0.843)

Agent: How does the webhook validation work?
→ [calls ask_codebase("webhook validation")]
→ Returns: "In src/payments/webhook.py, validate_signature() computes..."

Agent: Remember: we switched from PayPal to Stripe in Feb 2026
→ [calls remember("switched from PayPal to Stripe in Feb 2026", tags=["payments"])]
→ Memory stored.

# Later session —
Agent: What payment provider do we use?
→ [calls recall("payment provider")]
→ Returns: "switched from PayPal to Stripe in Feb 2026"
```

---

## Notes

- The MCP server is **stateless** per request — it reads from the local `.embex/` database on each call.
- Multiple agents can share the same MCP server instance and the same memory store.
- Tag memories with `--agent <name>` to namespace them per agent.
