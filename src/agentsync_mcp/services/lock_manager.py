from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from agentsync_mcp.db.database import Database
from agentsync_mcp.models.lock import LockInfo

logger = logging.getLogger(__name__)


class LockManager:
    """Thread-safe, in-memory lock manager with SQLite persistence.

    Design:
    - In-memory dict for sub-millisecond lock checks.
    - SQLite for persistence and crash recovery.
    - asyncio.Lock for safe concurrent access within the event loop.
    - Automatic expiration via a background cleanup task.
    """

    def __init__(self, db: Database, cleanup_interval: int = 60):
        self.db = db
        self._locks: dict[str, LockInfo] = {}
        self._mu = asyncio.Lock()
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Restore locks from DB and start the cleanup loop."""
        await self._restore_locks()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("LockManager started")

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("LockManager stopped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def acquire_lock(
        self,
        file_path: str,
        agent_id: str,
        description: str,
        ttl_seconds: int = 1800,
    ) -> dict[str, Any]:
        """Attempt to acquire a lock on a file.

        Returns a dict with at least ``{"success": bool}``.
        On failure it also contains info about the blocking lock.
        """
        async with self._mu:
            if file_path in self._locks:
                existing = self._locks[file_path]

                if existing.is_expired():
                    logger.info("Lock on %s expired, removing", file_path)
                    del self._locks[file_path]
                elif existing.agent_id == agent_id:
                    # Renew
                    existing.expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
                    await self.db.update_lock_expiry(file_path, existing.expires_at)
                    logger.info("Renewed lock on %s for %s", file_path, agent_id)
                    return {"success": True}
                else:
                    logger.warning("Lock denied on %s: held by %s", file_path, existing.agent_id)
                    return {
                        "success": False,
                        "locked_by": existing.agent_id,
                        "locked_at": existing.locked_at.isoformat(),
                        "description": existing.description,
                        "expires_at": existing.expires_at.isoformat(),
                    }

            lock_info = LockInfo(
                file_path=file_path,
                agent_id=agent_id,
                description=description,
                locked_at=datetime.now(),
                expires_at=datetime.now() + timedelta(seconds=ttl_seconds),
            )
            self._locks[file_path] = lock_info
            await self.db.create_lock(lock_info)
            await self.db.log_event(
                "lock_acquired", agent_id, {"file": file_path, "description": description}
            )
            logger.info("Lock acquired on %s by %s", file_path, agent_id)
            return {"success": True}

    async def release_lock(self, file_path: str, agent_id: str) -> bool:
        """Release a lock. Only the owner can release."""
        async with self._mu:
            lock_info = self._locks.get(file_path)
            if lock_info is None:
                logger.warning("Attempted to release non-existent lock on %s", file_path)
                return False

            if lock_info.agent_id != agent_id:
                logger.warning(
                    "Agent %s tried to release lock held by %s", agent_id, lock_info.agent_id
                )
                return False

            del self._locks[file_path]
            await self.db.release_lock(file_path, agent_id)
            await self.db.log_event("lock_released", agent_id, {"file": file_path})
            logger.info("Lock released on %s by %s", file_path, agent_id)
            return True

    async def get_lock_info(self, file_path: str) -> dict[str, Any] | None:
        async with self._mu:
            lock_info = self._locks.get(file_path)
            if lock_info is None:
                return None
            if lock_info.is_expired():
                del self._locks[file_path]
                return None
            return lock_info.model_dump(mode="json")

    async def get_all_locks(self) -> list[dict[str, Any]]:
        async with self._mu:
            self._purge_expired()
            return [lock.model_dump(mode="json") for lock in self._locks.values()]

    async def get_locks_by_agent(self, agent_id: str) -> list[dict[str, Any]]:
        async with self._mu:
            self._purge_expired()
            return [
                lock.model_dump(mode="json")
                for lock in self._locks.values()
                if lock.agent_id == agent_id
            ]

    async def release_all_agent_locks(self, agent_id: str) -> int:
        async with self._mu:
            to_release = [fp for fp, lk in self._locks.items() if lk.agent_id == agent_id]
            for fp in to_release:
                del self._locks[fp]
                await self.db.release_lock(fp, agent_id)
            logger.info("Released %d locks for agent %s", len(to_release), agent_id)
            return len(to_release)

    async def get_active_lock_count(self) -> int:
        async with self._mu:
            self._purge_expired()
            return len(self._locks)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _purge_expired(self) -> None:
        """Remove expired locks from in-memory state (caller must hold _mu)."""
        expired = [fp for fp, lk in self._locks.items() if lk.is_expired()]
        for fp in expired:
            del self._locks[fp]

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired locks in memory and DB."""
        while True:
            await asyncio.sleep(self._cleanup_interval)
            async with self._mu:
                self._purge_expired()
            count = await self.db.cleanup_expired_locks()
            if count:
                logger.info("Cleaned up %d expired locks from DB", count)

    async def _restore_locks(self) -> None:
        """Restore non-expired locks from DB on startup."""
        rows = await self.db.get_active_locks()
        now = datetime.now()
        for row in rows:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at > now:
                self._locks[row["file_path"]] = LockInfo(
                    file_path=row["file_path"],
                    agent_id=row["agent_id"],
                    description=row["description"] or "",
                    locked_at=datetime.fromisoformat(row["locked_at"]),
                    expires_at=expires_at,
                )
        logger.info("Restored %d active locks from database", len(self._locks))
