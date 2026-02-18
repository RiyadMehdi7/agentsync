from __future__ import annotations

from pathlib import Path

import pytest

from agentsync_mcp.db.database import Database
from agentsync_mcp.services.conflict_analyzer import ConflictAnalyzer
from agentsync_mcp.services.event_bus import EventBus
from agentsync_mcp.services.lock_manager import LockManager
from agentsync_mcp.services.work_queue import WorkQueue
from agentsync_mcp.utils.config import Config


@pytest.fixture
async def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    await database.initialize()
    return database


@pytest.fixture
async def lock_manager(db: Database) -> LockManager:
    lm = LockManager(db, cleanup_interval=3600)  # long interval so it won't fire in tests
    await lm.start()
    yield lm  # type: ignore[misc]
    await lm.stop()


@pytest.fixture
def work_queue(db: Database) -> WorkQueue:
    return WorkQueue(db)


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def config() -> Config:
    return Config()


@pytest.fixture
def conflict_analyzer(db: Database, work_queue: WorkQueue, config: Config) -> ConflictAnalyzer:
    return ConflictAnalyzer(db, work_queue, config)
