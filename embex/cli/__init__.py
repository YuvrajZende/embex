"""
CLI app assembly — wires all sub-commands into the Typer app.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="embex",
    help="Embex — local-first memory layer for AI agents.",
    add_completion=False,
    rich_markup_mode="rich",
)

# Import and register sub-commands
from embex.cli.init import init_command      # noqa: E402
from embex.cli.watch import watch_command    # noqa: E402
from embex.cli.query import query_command    # noqa: E402
from embex.cli.log import log_command        # noqa: E402
from embex.cli.diff import diff_command      # noqa: E402
from embex.cli.restore import restore_command  # noqa: E402
from embex.cli.status import status_command  # noqa: E402
from embex.cli.serve_mcp import serve_mcp_command  # noqa: E402
from embex.cli.search import search_command  # noqa: E402
from embex.cli.stats import stats_command  # noqa: E402
from embex.cli.ignore import ignore_command  # noqa: E402
from embex.cli.explain import explain_command  # noqa: E402
from embex.cli.similar import similar_command  # noqa: E402
from embex.cli.ask import ask_command          # noqa: E402
from embex.cli.memory import memory_app        # noqa: E402

app.command(name="init")(init_command)
app.command(name="watch")(watch_command)
app.command(name="query")(query_command)
app.command(name="ask")(ask_command)
app.command(name="log")(log_command)
app.command(name="diff")(diff_command)
app.command(name="restore")(restore_command)
app.command(name="status")(status_command)
app.command(name="serve-mcp")(serve_mcp_command)
app.command(name="search")(search_command)
app.command(name="stats")(stats_command)
app.command(name="ignore")(ignore_command)
app.command(name="explain")(explain_command)
app.command(name="similar")(similar_command)
app.add_typer(memory_app, name="memory")
