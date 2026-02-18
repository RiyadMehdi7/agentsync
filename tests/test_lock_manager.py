from __future__ import annotations

import pytest

from agentsync_mcp.services.lock_manager import LockManager


@pytest.mark.asyncio
class TestLockManager:
    async def test_acquire_and_release(self, lock_manager: LockManager) -> None:
        result = await lock_manager.acquire_lock(
            "src/auth.py", "agent-1", "Fix auth bug", ttl_seconds=60
        )
        assert result["success"] is True

        info = await lock_manager.get_lock_info("src/auth.py")
        assert info is not None
        assert info["agent_id"] == "agent-1"

        released = await lock_manager.release_lock("src/auth.py", "agent-1")
        assert released is True

        info = await lock_manager.get_lock_info("src/auth.py")
        assert info is None

    async def test_lock_conflict(self, lock_manager: LockManager) -> None:
        r1 = await lock_manager.acquire_lock("src/auth.py", "agent-1", "Fix auth", ttl_seconds=60)
        assert r1["success"] is True

        r2 = await lock_manager.acquire_lock(
            "src/auth.py", "agent-2", "Refactor auth", ttl_seconds=60
        )
        assert r2["success"] is False
        assert r2["locked_by"] == "agent-1"

    async def test_lock_renewal(self, lock_manager: LockManager) -> None:
        r1 = await lock_manager.acquire_lock("src/auth.py", "agent-1", "Fix auth", ttl_seconds=10)
        assert r1["success"] is True

        # Same agent can re-acquire (renewal)
        r2 = await lock_manager.acquire_lock("src/auth.py", "agent-1", "Fix auth", ttl_seconds=60)
        assert r2["success"] is True

    async def test_expired_lock_freed(self, lock_manager: LockManager) -> None:
        # Acquire with 0-second TTL → immediately expired
        r1 = await lock_manager.acquire_lock("src/auth.py", "agent-1", "Quick edit", ttl_seconds=0)
        assert r1["success"] is True

        # Another agent should be able to acquire since it's expired
        r2 = await lock_manager.acquire_lock("src/auth.py", "agent-2", "Another edit", ttl_seconds=60)
        assert r2["success"] is True

    async def test_release_wrong_owner(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire_lock("src/auth.py", "agent-1", "Fix auth", ttl_seconds=60)

        released = await lock_manager.release_lock("src/auth.py", "agent-2")
        assert released is False

    async def test_release_nonexistent(self, lock_manager: LockManager) -> None:
        released = await lock_manager.release_lock("nonexistent.py", "agent-1")
        assert released is False

    async def test_get_all_locks(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire_lock("a.py", "agent-1", "work on a", ttl_seconds=60)
        await lock_manager.acquire_lock("b.py", "agent-2", "work on b", ttl_seconds=60)

        locks = await lock_manager.get_all_locks()
        assert len(locks) == 2

    async def test_get_locks_by_agent(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire_lock("a.py", "agent-1", "work", ttl_seconds=60)
        await lock_manager.acquire_lock("b.py", "agent-1", "work", ttl_seconds=60)
        await lock_manager.acquire_lock("c.py", "agent-2", "work", ttl_seconds=60)

        agent1_locks = await lock_manager.get_locks_by_agent("agent-1")
        assert len(agent1_locks) == 2

    async def test_release_all_agent_locks(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire_lock("a.py", "agent-1", "work", ttl_seconds=60)
        await lock_manager.acquire_lock("b.py", "agent-1", "work", ttl_seconds=60)

        count = await lock_manager.release_all_agent_locks("agent-1")
        assert count == 2
        assert await lock_manager.get_active_lock_count() == 0

    async def test_active_lock_count(self, lock_manager: LockManager) -> None:
        assert await lock_manager.get_active_lock_count() == 0
        await lock_manager.acquire_lock("a.py", "agent-1", "work", ttl_seconds=60)
        assert await lock_manager.get_active_lock_count() == 1
