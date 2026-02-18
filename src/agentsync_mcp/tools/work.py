from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agentsync_mcp.services.work_queue import WorkQueue


def register(mcp: FastMCP, work_queue: WorkQueue) -> None:
    """Register work-tracking MCP tools."""

    @mcp.tool()
    async def get_active_work(agent_id: str | None = None) -> list[dict]:
        """Get the list of active work items across all agents.

        Use this to understand what other agents are currently working on
        so you can avoid conflicts.

        Args:
            agent_id: Optional — filter to a specific agent's work
        """
        return await work_queue.get_active_work(agent_id)
