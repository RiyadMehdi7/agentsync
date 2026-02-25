from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.work_queue import WorkQueue


def register(mcp: FastMCP, work_queue: WorkQueue, db: Database, agent_id: str) -> None:
    """Register work-tracking MCP tools."""

    @mcp.tool()
    async def get_active_work() -> list[dict]:
        """Get the list of all active work items across all agents.

        Use this to understand what other agents are currently working on
        so you can avoid conflicts and coordinate your work.
        """
        await db.touch_agent(agent_id)
        return await work_queue.get_active_work()

    @mcp.tool()
    async def get_active_sessions(stale_after_seconds: int = 90) -> list[dict]:
        """List live agent sessions auto-detected through the AgentSync MCP server.

        This shows connected Claude/Codex/etc. sessions with workspace and branch
        metadata so humans and agents can coordinate without manual registration.
        """
        await db.touch_agent(agent_id)
        return await db.get_active_sessions(stale_after_seconds=stale_after_seconds)
