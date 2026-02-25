from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.conflict_analyzer import ConflictAnalyzer
from agentsync_mcp.services.work_queue import WorkQueue


def register(
    mcp: FastMCP,
    conflict_analyzer: ConflictAnalyzer,
    work_queue: WorkQueue,
    db: Database,
    agent_id: str,
) -> None:
    """Register conflict-detection MCP tools."""

    @mcp.tool()
    async def register_agent_action(
        action: str,
        files: list[str],
        intent: str,
    ) -> dict:
        """Register an action for semantic conflict detection.

        Call this when you are about to modify, delete, create, or rename
        files. The server will check for semantic conflicts with other
        agents' recent work and warn you about issues.

        Args:
            action: Type of action — "modify", "delete", "create", or "rename"
            files: Files affected by the action
            intent: Plain-English description of what the change accomplishes
        """
        await db.touch_agent(agent_id)
        await work_queue.register_action(agent_id, action, files, intent)

        conflicts = await conflict_analyzer.detect_semantic_conflicts(
            agent_id=agent_id, files=files, intent=intent
        )

        return {"recorded": True, "conflicts": conflicts}

    @mcp.tool()
    async def get_conflict_suggestions(
        file: str,
        branch1: str,
        branch2: str,
    ) -> dict:
        """Get AI-powered merge suggestions for conflicting changes.

        When two branches have conflicting edits to the same file, call
        this to get an intelligent merge strategy with a confidence score.

        Args:
            file: File path with the conflict
            branch1: First branch name
            branch2: Second branch name
        """
        await db.touch_agent(agent_id)
        return await conflict_analyzer.generate_merge_suggestion(file, branch1, branch2)
