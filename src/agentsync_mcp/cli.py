from __future__ import annotations

import asyncio
import sys

import click

from agentsync_mcp import __version__


@click.group()
@click.version_option(version=__version__, prog_name="agentsync-mcp")
def main() -> None:
    """AgentSync MCP — Multi-Agent Code Coordination Platform."""


@main.command()
@click.option(
    "--db-path",
    default="data/agentsync.db",
    show_default=True,
    help="Path for the SQLite database file.",
)
def init(db_path: str) -> None:
    """Initialize the AgentSync database."""
    from agentsync_mcp.db.database import Database

    async def _init() -> None:
        db = Database(db_path)
        await db.initialize()
        await db.close()
        click.echo(f"Database initialized at {db_path}")

    asyncio.run(_init())


@main.command()
def start() -> None:
    """Start the AgentSync MCP server."""
    from agentsync_mcp.server import mcp

    click.echo("Starting AgentSync MCP Server...")
    mcp.run()


@main.command()
def version() -> None:
    """Print the version and exit."""
    click.echo(f"agentsync-mcp {__version__}")


if __name__ == "__main__":
    main()
