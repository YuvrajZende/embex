"""
embex serve-mcp — start the MCP server for AI agent integration.
"""

from __future__ import annotations

import typer
from embex.utils.display import info


def serve_mcp_command() -> None:
    """Start the Embex MCP server (stdio transport) for AI agents."""
    info("Starting Embex MCP Server (stdio transport)...")
    info("Connect from Claude Desktop, Cursor, or any MCP-compatible client.")

    from embex.mcp_server import run_mcp_server
    run_mcp_server()
