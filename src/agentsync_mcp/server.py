from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.conflict_analyzer import ConflictAnalyzer
from agentsync_mcp.services.event_bus import EventBus
from agentsync_mcp.services.identity import generate_agent_id
from agentsync_mcp.services.lock_manager import LockManager
from agentsync_mcp.services.work_queue import WorkQueue
from agentsync_mcp.tools import conflicts as conflict_tools
from agentsync_mcp.tools import locks as lock_tools
from agentsync_mcp.tools import work as work_tools
from agentsync_mcp.utils.config import get_config
from agentsync_mcp.utils.logger import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle for AgentSync."""
    config = get_config()

    # --- Database ---
    db = Database(config.db_path)
    await db.initialize()

    # --- Services ---
    lock_manager = LockManager(db, cleanup_interval=config.lock_cleanup_interval)
    await lock_manager.start()

    work_queue = WorkQueue(db)
    event_bus = EventBus()
    conflict_analyzer = ConflictAnalyzer(db, work_queue, config)

    # --- Identity ---
    my_agent_id = generate_agent_id()
    logger.info("This agent's ID: %s", my_agent_id)

    # --- Register MCP tools ---
    lock_tools.register(server, lock_manager, work_queue, event_bus, db, my_agent_id)
    work_tools.register(server, work_queue)
    conflict_tools.register(server, conflict_analyzer, work_queue, db, my_agent_id)

    # --- Register MCP resource ---
    @server.resource("agentsync://stats")
    async def get_stats() -> str:
        active_locks = await lock_manager.get_active_lock_count()
        active_work = len(await work_queue.get_active_work())
        agents = await work_queue.get_all_agents()
        return (
            "AgentSync Status:\n"
            f"- Active Locks: {active_locks}\n"
            f"- Active Work Items: {active_work}\n"
            f"- Connected Agents: {len(agents)}\n"
        )

    logger.info("AgentSync MCP Server ready")

    try:
        yield
    finally:
        await lock_manager.stop()
        logger.info("AgentSync MCP Server stopped")


def create_server() -> FastMCP:
    """Build and return the configured FastMCP server."""
    config = get_config()
    setup_logging(config.log_level)

    server = FastMCP("AgentSync", lifespan=lifespan)
    return server


# Module-level instance used by the CLI and ``python -m``
mcp = create_server()

if __name__ == "__main__":
    mcp.run()
