from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.event_bus import EventBus
from agentsync_mcp.services.lock_manager import LockManager
from agentsync_mcp.services.work_queue import WorkQueue


def register(
    mcp: FastMCP,
    lock_manager: LockManager,
    work_queue: WorkQueue,
    event_bus: EventBus,
    db: Database,
) -> None:
    """Register lock-related MCP tools."""

    @mcp.tool()
    async def request_file_lock(
        files: list[str],
        description: str,
        agent_id: str,
        ttl_seconds: int = 1800,
    ) -> dict:
        """Request exclusive locks on one or more files.

        Before modifying files, call this tool to claim exclusive access.
        If another agent already holds a lock you will receive details about
        the blocking lock so you can coordinate.

        Args:
            files: List of file paths to lock (e.g. ["src/auth.py"])
            description: What you plan to do (e.g. "Fix login bug")
            agent_id: Your unique identifier (e.g. "claude-code-alice")
            ttl_seconds: Lock timeout in seconds (default 1800 = 30 min)
        """
        await db.register_agent(agent_id)

        locked: list[str] = []
        blocked: list[dict] = []

        for file_path in files:
            result = await lock_manager.acquire_lock(
                file_path=file_path,
                agent_id=agent_id,
                description=description,
                ttl_seconds=ttl_seconds,
            )
            if result["success"]:
                locked.append(file_path)
            else:
                blocked.append(
                    {
                        "file": file_path,
                        "locked_by": result["locked_by"],
                        "locked_at": result["locked_at"],
                        "description": result["description"],
                        "expires_at": result["expires_at"],
                    }
                )

        if locked:
            await work_queue.create_work_item(agent_id, description, locked)
            await event_bus.publish(
                "lock_acquired",
                {"agent_id": agent_id, "files": locked, "description": description},
            )

        return {"success": len(blocked) == 0, "locked": locked, "blocked": blocked}

    @mcp.tool()
    async def release_file_lock(
        files: list[str],
        agent_id: str,
        commit_hash: str | None = None,
    ) -> dict:
        """Release locks on files after completing work.

        Always release your locks when done so other agents can proceed.

        Args:
            files: Files to unlock
            agent_id: Your agent id (must be the lock owner)
            commit_hash: Optional git commit hash if work was committed
        """
        released: list[str] = []
        for file_path in files:
            if await lock_manager.release_lock(file_path, agent_id):
                released.append(file_path)

        if commit_hash:
            await work_queue.complete_work(agent_id, commit_hash)

        if released:
            await event_bus.publish(
                "lock_released",
                {"agent_id": agent_id, "files": released, "commit_hash": commit_hash},
            )

        return {"success": True, "released": released}

    @mcp.tool()
    async def check_file_status(files: list[str]) -> list[dict]:
        """Check the lock status of one or more files without acquiring locks.

        Use this to see if files are available before starting work.

        Args:
            files: File paths to check
        """
        statuses: list[dict] = []
        for file_path in files:
            info = await lock_manager.get_lock_info(file_path)
            statuses.append(
                {
                    "file": file_path,
                    "locked": info is not None,
                    "locked_by": info["agent_id"] if info else None,
                    "description": info["description"] if info else None,
                    "expires_at": info["expires_at"] if info else None,
                }
            )
        return statuses
