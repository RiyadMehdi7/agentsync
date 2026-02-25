from __future__ import annotations

import asyncio

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


def _run_auto_wrapper(
    *,
    client: str,
    command: tuple[str, ...],
    db_path: str,
    poll_interval: float,
    ttl_seconds: int,
    description: str | None,
) -> None:
    from agentsync_mcp.services.auto_coordinator import AutoCoordinationOptions, AutoCoordinator

    if not command:
        raise click.UsageError(
            "Missing command to wrap. Example: agentsync-mcp auto --client codex -- codex"
        )

    async def _run() -> int:
        runner = AutoCoordinator(
            AutoCoordinationOptions(
                client=client,
                command=list(command),
                db_path=db_path,
                poll_interval=poll_interval,
                ttl_seconds=ttl_seconds,
                description=description,
            )
        )
        return await runner.run()

    code = asyncio.run(_run())
    raise SystemExit(code)


@main.command(
    context_settings={"ignore_unknown_options": True},
)
@click.option(
    "--client",
    type=click.Choice(["codex", "claude", "auto"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Agent client type for metadata/session labeling.",
)
@click.option(
    "--db-path",
    default="data/agentsync.db",
    show_default=True,
    help="Path to the shared AgentSync SQLite database.",
)
@click.option(
    "--poll-interval",
    default=1.0,
    show_default=True,
    type=float,
    help="Seconds between git status scans for auto-locking.",
)
@click.option(
    "--ttl-seconds",
    default=1800,
    show_default=True,
    type=int,
    help="Lock TTL used for auto-acquired locks.",
)
@click.option(
    "--description",
    default=None,
    help="Optional lock description (otherwise generated from wrapped command).",
)
@click.argument("command", nargs=-1, type=click.UNPROCESSED)
def auto(
    client: str,
    db_path: str,
    poll_interval: float,
    ttl_seconds: int,
    description: str | None,
    command: tuple[str, ...],
) -> None:
    """Run a command with automatic AgentSync lock coordination."""
    _run_auto_wrapper(
        client=client,
        command=command,
        db_path=db_path,
        poll_interval=poll_interval,
        ttl_seconds=ttl_seconds,
        description=description,
    )


@main.command(
    "codex",
    context_settings={"ignore_unknown_options": True},
)
@click.option("--db-path", default="data/agentsync.db", show_default=True)
@click.option("--poll-interval", default=1.0, show_default=True, type=float)
@click.option("--ttl-seconds", default=1800, show_default=True, type=int)
@click.option("--description", default=None)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def codex_wrapper(
    db_path: str,
    poll_interval: float,
    ttl_seconds: int,
    description: str | None,
    args: tuple[str, ...],
) -> None:
    """Launch Codex with auto-coordination enabled."""
    _run_auto_wrapper(
        client="codex",
        command=("codex", *args),
        db_path=db_path,
        poll_interval=poll_interval,
        ttl_seconds=ttl_seconds,
        description=description,
    )


@main.command(
    "claude",
    context_settings={"ignore_unknown_options": True},
)
@click.option("--db-path", default="data/agentsync.db", show_default=True)
@click.option("--poll-interval", default=1.0, show_default=True, type=float)
@click.option("--ttl-seconds", default=1800, show_default=True, type=int)
@click.option("--description", default=None)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def claude_wrapper(
    db_path: str,
    poll_interval: float,
    ttl_seconds: int,
    description: str | None,
    args: tuple[str, ...],
) -> None:
    """Launch Claude with auto-coordination enabled."""
    _run_auto_wrapper(
        client="claude",
        command=("claude", *args),
        db_path=db_path,
        poll_interval=poll_interval,
        ttl_seconds=ttl_seconds,
        description=description,
    )


if __name__ == "__main__":
    main()
