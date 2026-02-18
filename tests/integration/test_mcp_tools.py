"""Integration tests that exercise MCP tools through the service layer.

These tests simulate the full flow an MCP client would follow:
lock → work → release.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.event_bus import EventBus
from agentsync_mcp.services.lock_manager import LockManager
from agentsync_mcp.services.work_queue import WorkQueue


@pytest.fixture
async def services(tmp_path: Path):
    db = Database(tmp_path / "integration.db")
    await db.initialize()

    lm = LockManager(db, cleanup_interval=3600)
    await lm.start()

    wq = WorkQueue(db)
    eb = EventBus()

    yield {"db": db, "lock_manager": lm, "work_queue": wq, "event_bus": eb}

    await lm.stop()


@pytest.mark.asyncio
class TestMCPToolFlow:
    async def test_full_lock_work_release_cycle(self, services: dict) -> None:
        db: Database = services["db"]
        lm: LockManager = services["lock_manager"]
        wq: WorkQueue = services["work_queue"]

        agent = "claude-code-alice"
        files = ["src/auth.py", "src/login.py"]

        # Register agent
        await db.register_agent(agent)

        # Lock files
        locked = []
        for f in files:
            r = await lm.acquire_lock(f, agent, "Fix auth bug", ttl_seconds=300)
            assert r["success"] is True
            locked.append(f)

        # Create work item
        wid = await wq.create_work_item(agent, "Fix auth bug", locked)
        assert wid > 0

        # Verify active work
        active = await wq.get_active_work(agent)
        assert len(active) == 1

        # Complete work and release
        await wq.complete_work(agent, commit_hash="abc123")
        for f in locked:
            await lm.release_lock(f, agent)

        # Verify clean state
        assert await lm.get_active_lock_count() == 0
        assert len(await wq.get_active_work(agent)) == 0

    async def test_multi_agent_lock_contention(self, services: dict) -> None:
        db: Database = services["db"]
        lm: LockManager = services["lock_manager"]

        await db.register_agent("agent-a")
        await db.register_agent("agent-b")

        # Agent A locks the file
        r1 = await lm.acquire_lock("shared.py", "agent-a", "Working on shared", ttl_seconds=300)
        assert r1["success"] is True

        # Agent B tries the same file — should be blocked
        r2 = await lm.acquire_lock("shared.py", "agent-b", "Also want shared", ttl_seconds=300)
        assert r2["success"] is False
        assert r2["locked_by"] == "agent-a"

        # Agent A releases
        await lm.release_lock("shared.py", "agent-a")

        # Now Agent B succeeds
        r3 = await lm.acquire_lock("shared.py", "agent-b", "Now I can work", ttl_seconds=300)
        assert r3["success"] is True

    async def test_event_bus_receives_lock_events(self, services: dict) -> None:
        db: Database = services["db"]
        lm: LockManager = services["lock_manager"]
        eb: EventBus = services["event_bus"]

        events: list[dict] = []

        async def on_event(event: dict) -> None:
            events.append(event)

        eb.subscribe("*", on_event)
        await db.register_agent("agent-1")

        # Simulate what the MCP tool does
        r = await lm.acquire_lock("a.py", "agent-1", "test", ttl_seconds=60)
        assert r["success"]
        await eb.publish("lock_acquired", {"agent_id": "agent-1", "files": ["a.py"]})

        await lm.release_lock("a.py", "agent-1")
        await eb.publish("lock_released", {"agent_id": "agent-1", "files": ["a.py"]})

        assert len(events) == 2
        assert events[0]["type"] == "lock_acquired"
        assert events[1]["type"] == "lock_released"
