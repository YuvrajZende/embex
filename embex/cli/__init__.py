"""
CLI module — registers all the commands for the embex tool.
"""

import typer

app = typer.Typer(
    name="embex",
    help="Embex — local code embedding and search tool.",
    add_completion=False,
    rich_markup_mode="rich",
)

# Import the command functions
from embex.cli.init import init_command
from embex.cli.watch import watch_command
from embex.cli.restore import restore_command
from embex.cli.search import search_command
from embex.cli.explain import explain_command
from embex.cli.ask import ask_command

# Register commands
app.command(name="init")(init_command)
app.command(name="watch")(watch_command)
app.command(name="ask")(ask_command)
app.command(name="restore")(restore_command)
app.command(name="search")(search_command)
app.command(name="explain")(explain_command)
