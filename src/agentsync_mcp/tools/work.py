from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agentsync_mcp.services.work_queue import WorkQueue


def register(mcp: FastMCP, work_queue: WorkQueue) -> None:
    """Register work-tracking MCP tools."""

    @mcp.tool()
    async def get_active_work() -> list[dict]:
        """Get the list of all active work items across all agents.

        Use this to understand what other agents are currently working on
        so you can avoid conflicts and coordinate your work.
        """
        return await work_queue.get_active_work()
