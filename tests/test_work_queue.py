from __future__ import annotations

import pytest

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.work_queue import WorkQueue


@pytest.mark.asyncio
class TestWorkQueue:
    async def test_create_and_get_work(self, work_queue: WorkQueue, db: Database) -> None:
        await db.register_agent("agent-1")
        work_id = await work_queue.create_work_item(
            "agent-1", "Fix login bug", ["src/auth.py", "src/login.py"]
        )
        assert work_id > 0

        active = await work_queue.get_active_work()
        assert len(active) == 1
        assert active[0]["agent_id"] == "agent-1"
        assert active[0]["files"] == ["src/auth.py", "src/login.py"]

    async def test_filter_by_agent(self, work_queue: WorkQueue, db: Database) -> None:
        await db.register_agent("agent-1")
        await db.register_agent("agent-2")
        await work_queue.create_work_item("agent-1", "Task A", ["a.py"])
        await work_queue.create_work_item("agent-2", "Task B", ["b.py"])

        agent1_work = await work_queue.get_active_work("agent-1")
        assert len(agent1_work) == 1
        assert agent1_work[0]["description"] == "Task A"

    async def test_complete_work(self, work_queue: WorkQueue, db: Database) -> None:
        await db.register_agent("agent-1")
        await work_queue.create_work_item("agent-1", "Fix bug", ["a.py"])

        ok = await work_queue.complete_work("agent-1", commit_hash="abc123")
        assert ok is True

        active = await work_queue.get_active_work("agent-1")
        assert len(active) == 0

    async def test_complete_no_active_work(self, work_queue: WorkQueue) -> None:
        ok = await work_queue.complete_work("nonexistent-agent")
        assert ok is False

    async def test_register_action(self, work_queue: WorkQueue, db: Database) -> None:
        await db.register_agent("agent-1")
        action_id = await work_queue.register_action(
            "agent-1", "modify", ["src/auth.py"], "Replace MD5 with bcrypt"
        )
        assert action_id > 0

    async def test_get_recent_actions(self, work_queue: WorkQueue, db: Database) -> None:
        await db.register_agent("agent-1")
        await work_queue.register_action("agent-1", "modify", ["a.py"], "Change A")
        await work_queue.register_action("agent-1", "create", ["b.py"], "Create B")

        all_actions = await work_queue.get_recent_actions()
        assert len(all_actions) == 2

        a_actions = await work_queue.get_recent_actions("a.py")
        assert len(a_actions) == 1
        assert a_actions[0]["intent"] == "Change A"

    async def test_get_all_agents(self, work_queue: WorkQueue, db: Database) -> None:
        await db.register_agent("agent-1")
        await db.register_agent("agent-2")

        agents = await work_queue.get_all_agents()
        assert set(agents) == {"agent-1", "agent-2"}
