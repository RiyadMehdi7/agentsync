from __future__ import annotations

import logging
from typing import Any

from agentsync_mcp.db.database import Database

logger = logging.getLogger(__name__)


class WorkQueue:
    """Manages work items and agent actions."""

    def __init__(self, db: Database):
        self.db = db

    async def create_work_item(
        self, agent_id: str, description: str, files: list[str]
    ) -> int:
        work_id = await self.db.create_work_item(agent_id, description, files)
        await self.db.log_event(
            "work_started",
            agent_id,
            {"work_id": work_id, "description": description, "files": files},
        )
        logger.info("Created work item #%d for %s", work_id, agent_id)
        return work_id

    async def complete_work(
        self, agent_id: str, commit_hash: str | None = None
    ) -> bool:
        ok = await self.db.complete_work_item(agent_id, commit_hash)
        if ok:
            await self.db.log_event(
                "work_completed", agent_id, {"commit_hash": commit_hash}
            )
            logger.info("Completed work for %s", agent_id)
        else:
            logger.warning("No active work found for %s", agent_id)
        return ok

    async def get_active_work(
        self, agent_id: str | None = None
    ) -> list[dict[str, Any]]:
        rows = await self.db.get_active_work_items(agent_id)
        return [
            {
                "work_id": r["id"],
                "agent_id": r["agent_id"],
                "description": r["description"],
                "files": r["files"],
                "started_at": r["started_at"],
                "status": r["status"],
            }
            for r in rows
        ]

    async def register_action(
        self,
        agent_id: str,
        action_type: str,
        files: list[str],
        intent: str,
    ) -> int:
        action_id = await self.db.register_action(agent_id, action_type, files, intent)
        logger.info(
            "Registered action #%d: %s - %s on %s", action_id, agent_id, action_type, files
        )
        return action_id

    async def get_recent_actions(
        self, file_path: str | None = None, hours: int = 24
    ) -> list[dict[str, Any]]:
        return await self.db.get_recent_actions(file_path, hours)

    async def get_all_agents(self) -> list[str]:
        return await self.db.get_all_active_agents()
