from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from agentsync_mcp.db.database import Database
from agentsync_mcp.models.lock import LockInfo


@pytest.mark.asyncio
class TestDatabase:
    async def test_register_agent(self, db: Database) -> None:
        await db.register_agent("cursor-alice", "cursor")
        agents = await db.get_all_active_agents()
        assert "cursor-alice" in agents

    async def test_register_agent_idempotent(self, db: Database) -> None:
        await db.register_agent("agent-1")
        await db.register_agent("agent-1")  # should not raise
        agents = await db.get_all_active_agents()
        assert agents.count("agent-1") == 1

    async def test_active_sessions_include_metadata(self, db: Database) -> None:
        await db.register_agent(
            "codex-host-123-abc123",
            "codex",
            session={
                "client_name": "Codex",
                "session_label": "Codex-agentsync-main-123",
                "host": "host",
                "pid": 123,
                "cwd": "/repo",
                "repo_root": "/repo",
                "repo_name": "agentsync",
                "git_branch": "main",
                "transport": "stdio",
                "metadata": {"detected_from": "env:CODEX_*"},
            },
        )

        sessions = await db.get_active_sessions(stale_after_seconds=3600)
        assert len(sessions) == 1
        assert sessions[0]["agent_type"] == "codex"
        assert sessions[0]["client_name"] == "Codex"
        assert sessions[0]["metadata"]["detected_from"] == "env:CODEX_*"

    async def test_create_and_get_lock(self, db: Database) -> None:
        lock = LockInfo(
            file_path="a.py",
            agent_id="agent-1",
            description="work",
            locked_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=30),
        )
        lock_id = await db.create_lock(lock)
        assert lock_id > 0

        locks = await db.get_active_locks()
        assert len(locks) == 1
        assert locks[0]["file_path"] == "a.py"

    async def test_release_lock(self, db: Database) -> None:
        lock = LockInfo(
            file_path="a.py",
            agent_id="agent-1",
            description="work",
            locked_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=30),
        )
        await db.create_lock(lock)
        await db.release_lock("a.py", "agent-1")

        locks = await db.get_active_locks()
        assert len(locks) == 0

    async def test_cleanup_expired_locks(self, db: Database) -> None:
        lock = LockInfo(
            file_path="a.py",
            agent_id="agent-1",
            description="work",
            locked_at=datetime.now() - timedelta(hours=1),
            expires_at=datetime.now() - timedelta(minutes=1),  # already expired
        )
        await db.create_lock(lock)
        count = await db.cleanup_expired_locks()
        assert count == 1

    async def test_work_item_lifecycle(self, db: Database) -> None:
        await db.register_agent("agent-1")
        wid = await db.create_work_item("agent-1", "Fix bug", ["a.py"])
        assert wid > 0

        items = await db.get_active_work_items("agent-1")
        assert len(items) == 1

        ok = await db.complete_work_item("agent-1", "abc123")
        assert ok is True

        items = await db.get_active_work_items("agent-1")
        assert len(items) == 0

    async def test_action_registration(self, db: Database) -> None:
        await db.register_agent("agent-1")
        aid = await db.register_action("agent-1", "modify", ["a.py"], "Change A")
        assert aid > 0

        actions = await db.get_recent_actions("a.py")
        assert len(actions) == 1

    async def test_log_event(self, db: Database) -> None:
        # Should not raise
        await db.log_event("test_event", "agent-1", {"key": "value"})

    async def test_create_conflict(self, db: Database) -> None:
        await db.register_agent("agent-1")
        await db.register_agent("agent-2")
        cid = await db.create_conflict(
            "a.py", "agent-1", "agent-2", "semantic", "high", "Both modifying auth"
        )
        assert cid > 0
